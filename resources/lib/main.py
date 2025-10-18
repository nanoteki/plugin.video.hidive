import sys
import os
from typing import Optional, Dict, List, Any
try:
    from urlparse import parse_qs
except ImportError:
    from urllib.parse import parse_qs
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

# Setup path for local imports
ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo('path')
sys.path.insert(0, os.path.join(ADDON_PATH, 'resources', 'lib'))

from hidive_api import HidiveAPI
from config import AppConfig, LanguageConfig, create_config, update_auth_settings, has_credentials, has_auth_token, has_active_profile, get_language_config
from data_transforms import *
from ui_builders import *
from utils import *
from subtitle_handler import process_subtitle_list, cleanup_old_cache_files, get_cache_info

# ============================================================================
# HANDLER FUNCTIONS (defined first to avoid forward reference issues)
# ============================================================================

def handle_logout() -> None:
    """
    Handler for logout functionality.
    """
    update_auth_settings(ADDON, '', '')
    refresh_container()


def handle_session_expired() -> None:
    """
    Handler for expired session scenarios.
    """
    handle_logout()
    show_error_dialog("Session Expired", "Your session has expired. Please log in again.")
    refresh_container()


def handle_main_menu(api: HidiveAPI, config: AppConfig) -> None:
    """
    Handler for main menu display using functional approach.

    Args:
        api: HiDive API instance
        config: Application configuration
    """
    set_plugin_category(config.addon_handle, 'Main Menu')

    # New menu layout: Search, Dashboard, Watchlists, Profile, Logout

    # Get dashboard data using user-configured parameters (with API limits enforced)
    safe_buckets = min(config.dashboard_buckets_count, 10)  # Enforce API limit
    safe_entries = min(config.dashboard_entries_per_bucket, 50)  # Reasonable limit

    dashboard_result = safe_api_call(
        api.get_dashboard,
        buckets_count=safe_buckets,
        entries_per_bucket=safe_entries,
        enable_pagination=config.enable_dashboard_pagination
    )
    if not dashboard_result.is_ok():
        xbmc.log(f"HIDIVE: Failed to get dashboard, trying safe method", level=xbmc.LOGWARNING)
        # Try safe method as fallback
        dashboard_result = safe_api_call(api.get_dashboard_safe)
        if not dashboard_result.is_ok():
            xbmc.log(f"HIDIVE: Safe dashboard loading also failed", level=xbmc.LOGERROR)
            handle_session_expired()
            return

    # Build new menu layout: Search, Dashboard, Watchlists, Profile, Logout
    buckets = dashboard_result.data.get('buckets', [])
    if buckets and all(bucket.get('type') and bucket.get('exid') for bucket in buckets):
        # Use enhanced menu items
        menu_items = build_enhanced_main_menu_items(buckets, config.base_url)
        xbmc.log(f"HIDIVE: Using enhanced main menu layout", level=xbmc.LOGINFO)
    elif buckets:
        # Fallback to regular menu items
        bucket_names = extract_bucket_names(dashboard_result.data)
        menu_items = build_main_menu_items(bucket_names, config.base_url)
        xbmc.log(f"HIDIVE: Using regular main menu layout", level=xbmc.LOGINFO)
    else:
        xbmc.log("HIDIVE: No buckets found in dashboard", level=xbmc.LOGWARNING)
        handle_session_expired()
        return

    add_directory_items(config.addon_handle, menu_items)
    end_directory(config.addon_handle)


def handle_dashboard_menu(api: HidiveAPI, config: AppConfig) -> None:
    """
    Handler for dashboard submenu display.

    Args:
        api: HiDive API instance
        config: Application configuration
    """
    set_plugin_category(config.addon_handle, 'Dashboard')

    # Get dashboard data using user-configured parameters
    safe_buckets = min(config.dashboard_buckets_count, 10)  # Enforce API limit
    safe_entries = min(config.dashboard_entries_per_bucket, 50)  # Reasonable limit

    dashboard_result = safe_api_call(
        api.get_dashboard,
        buckets_count=safe_buckets,
        entries_per_bucket=safe_entries,
        enable_pagination=config.enable_dashboard_pagination
    )
    if not dashboard_result.is_ok():
        xbmc.log(f"HIDIVE: Failed to get dashboard, trying safe method", level=xbmc.LOGWARNING)
        # Try safe method as fallback
        dashboard_result = safe_api_call(api.get_dashboard_safe)
        if not dashboard_result.is_ok():
            xbmc.log(f"HIDIVE: Safe dashboard loading also failed", level=xbmc.LOGERROR)
            handle_session_expired()
            return

    # Build dashboard submenu items
    buckets = dashboard_result.data.get('buckets', [])
    if buckets and all(bucket.get('type') and bucket.get('exid') for bucket in buckets):
        # Use enhanced dashboard menu items
        dashboard_items = build_enhanced_dashboard_menu_items(buckets, config.base_url)
        xbmc.log(f"HIDIVE: Using enhanced dashboard submenu with {len(buckets)} buckets", level=xbmc.LOGINFO)
    elif buckets:
        # Fallback to regular dashboard menu items
        bucket_names = extract_bucket_names(dashboard_result.data)
        dashboard_items = build_dashboard_menu_items(bucket_names, config.base_url)
        xbmc.log(f"HIDIVE: Using regular dashboard submenu with {len(bucket_names)} buckets", level=xbmc.LOGINFO)
    else:
        xbmc.log("HIDIVE: No buckets found in dashboard", level=xbmc.LOGWARNING)
        handle_session_expired()
        return

    add_directory_items(config.addon_handle, dashboard_items)
    end_directory(config.addon_handle)


def handle_profile_selection(api: HidiveAPI, config: AppConfig) -> None:
    """
    Handler for profile selection.

    Args:
        api: HiDive API instance
        config: Application configuration
    """
    result = handle_profile_selection_flow(api)
    if result.is_ok():
        refresh_container()


def handle_bucket_listing(api: HidiveAPI, config: AppConfig, bucket_name: str) -> None:
    """
    Handler for bucket content listing using functional approach.

    Args:
        api: HiDive API instance
        config: Application configuration
        bucket_name: Name of the bucket to list
    """
    set_plugin_category(config.addon_handle, format_bucket_name(bucket_name))

    # Get dashboard data using user-configured parameters
    dashboard_result = safe_api_call(
        api.get_dashboard,
        buckets_count=config.dashboard_buckets_count,
        entries_per_bucket=config.dashboard_entries_per_bucket,
        enable_pagination=config.enable_dashboard_pagination
    )
    if not dashboard_result.is_ok():
        xbmc.log(f"HIDIVE: Failed to get dashboard for bucket {bucket_name}, trying safe method", level=xbmc.LOGWARNING)
        # Try safe method as fallback
        dashboard_result = safe_api_call(api.get_dashboard_safe)
        if not dashboard_result.is_ok():
            xbmc.log(f"HIDIVE: Safe dashboard loading also failed for bucket {bucket_name}", level=xbmc.LOGERROR)
            end_directory(config.addon_handle)
            return

    # Extract content from bucket
    content_items = extract_content_from_bucket(dashboard_result.data, bucket_name)
    if not content_items:
        xbmc.log(f"HIDIVE: No content found in bucket {bucket_name}", level=xbmc.LOGINFO)
        end_directory(config.addon_handle)
        return

    xbmc.log(f"HIDIVE: Found {len(content_items)} items in bucket {bucket_name}", level=xbmc.LOGINFO)

    # Process and display content items
    _process_bucket_content(content_items, config)

    end_directory(config.addon_handle)


def handle_enhanced_bucket_listing(api: HidiveAPI, config: AppConfig, bucket_name: str,
                                  bucket_type: str = None, bucket_exid: str = None) -> None:
    """
    Enhanced handler for bucket content listing with full pagination support.

    Args:
        api: HiDive API instance
        config: Application configuration
        bucket_name: Name of the bucket to list
        bucket_type: Type of the bucket (optional, will be looked up if not provided)
        bucket_exid: External ID of the bucket (optional, will be looked up if not provided)
    """
    set_plugin_category(config.addon_handle, format_bucket_name(bucket_name))

    # If bucket metadata not provided, get it from dashboard
    if not bucket_type or not bucket_exid:
        dashboard_result = safe_api_call(
            api.get_dashboard,
            buckets_count=config.dashboard_buckets_count,
            entries_per_bucket=config.dashboard_entries_per_bucket,
            enable_pagination=False  # Just get bucket metadata
        )

        if dashboard_result.is_ok():
            bucket_metadata = find_bucket_by_name(dashboard_result.data, bucket_name)
            if bucket_metadata:
                bucket_type = bucket_metadata.get('type', '')
                bucket_exid = bucket_metadata.get('exid', '')

    # Use enhanced bucket content API with full pagination
    if bucket_type and bucket_exid:
        bucket_content_result = safe_api_call(
            api.get_bucket_content,
            bucket_type=bucket_type,
            bucket_exid=bucket_exid,
            entries_per_page=config.dashboard_entries_per_bucket,
            enable_pagination=config.enable_dashboard_pagination
        )

        if bucket_content_result.is_ok():
            content_items = extract_content_from_bucket_data(bucket_content_result.data)
            if content_items:
                xbmc.log(f"HIDIVE: Enhanced bucket loading found {len(content_items)} items in {bucket_name}",
                        level=xbmc.LOGINFO)
                _process_bucket_content(content_items, config)
                end_directory(config.addon_handle)
                return

    # Fallback to regular bucket listing
    xbmc.log(f"HIDIVE: Falling back to regular bucket listing for {bucket_name}", level=xbmc.LOGINFO)
    handle_bucket_listing(api, config, bucket_name)


def handle_watchlists(api: HidiveAPI, config: AppConfig) -> None:
    """
    Handler for displaying user watchlists.

    Args:
        api: HiDive API instance
        config: Application configuration
    """
    set_plugin_category(config.addon_handle, 'My Watchlists')

    # Get user watchlists (basic endpoint without pagination parameters)
    watchlists_result = safe_api_call(api.get_watchlists)

    if not watchlists_result.is_ok():
        show_notification("Error", "Failed to load watchlists")
        end_directory(config.addon_handle)
        return

    watchlists_data = watchlists_result.data
    watchlists = watchlists_data.get('watchlists', [])  # Changed from 'items' to 'watchlists'

    if not watchlists:
        show_notification("No Watchlists", "You don't have any watchlists yet")
        end_directory(config.addon_handle)
        return

    # Create watchlist items
    watchlist_items = []
    for watchlist in watchlists:
        watchlist_id = str(watchlist.get('watchlistExternalId', ''))
        watchlist_name = watchlist.get('name', 'Unnamed Watchlist')

        # Get thumbnail from watchlist if available
        thumbnails = watchlist.get('thumbnails', [])
        # thumbnails is a list of URLs, not objects with 'source' property
        thumbnail = thumbnails[0] if thumbnails else ''

        # Create list item
        url = build_url(config.base_url, 'list_watchlist_content', watchlist_id=watchlist_id)
        list_item = create_list_item(
            watchlist_name,
            art={'thumb': thumbnail, 'poster': thumbnail},
            info={'plot': f'Watchlist: {watchlist_name}', 'mediatype': 'set'}
        )
        watchlist_items.append((url, list_item, True))

    add_directory_items(config.addon_handle, watchlist_items)
    xbmc.log(f"HIDIVE: Loaded {len(watchlists)} watchlists", level=xbmc.LOGINFO)
    end_directory(config.addon_handle)


def handle_watchlist_content(api: HidiveAPI, config: AppConfig, watchlist_id: str) -> None:
    """
    Handler for displaying content from a specific watchlist.

    Args:
        api: HiDive API instance
        config: Application configuration
        watchlist_id: ID of the watchlist to display
    """
    set_plugin_category(config.addon_handle, 'Watchlist Content')

    # Get watchlist content with pagination
    watchlist_content_result = safe_api_call(
        api.get_watchlist_content,
        watchlist_id=watchlist_id,
        entries_per_page=config.dashboard_entries_per_bucket,
        enable_pagination=config.enable_dashboard_pagination
    )

    if not watchlist_content_result.is_ok():
        show_notification("Error", "Failed to load watchlist content")
        end_directory(config.addon_handle)
        return

    watchlist_data = watchlist_content_result.data
    content_items = watchlist_data.get('content', [])

    if not content_items:
        show_notification("Empty Watchlist", "This watchlist is empty")
        end_directory(config.addon_handle)
        return

    # Debug logging to see the data structure
    if content_items:
        xbmc.log(f"HIDIVE DEBUG: First watchlist item structure: {content_items[0]}", level=xbmc.LOGINFO)

    # Process watchlist content items
    processed_items = []
    for item in content_items:
        processed_item = process_watchlist_content_item(item, config.base_url)
        if processed_item:
            processed_items.append(processed_item)

    add_directory_items(config.addon_handle, processed_items)
    xbmc.log(f"HIDIVE: Loaded {len(content_items)} items from watchlist {watchlist_id}", level=xbmc.LOGINFO)
    end_directory(config.addon_handle)


def process_watchlist_content_item(item: Dict[str, Any], base_url: str) -> Optional[tuple]:
    """
    Process a single watchlist content item.

    Args:
        item: Watchlist content item data
        base_url: Base URL for building navigation URLs

    Returns:
        Optional[tuple]: (url, list_item, is_folder) tuple or None if processing fails
    """
    try:
        # Try multiple possible field names for type
        item_type = item.get('type', item.get('contentType', ''))

        # Handle different content types and extract appropriate data
        if item_type == 'VOD_SEASON' and 'series' in item:
            # For seasons, use series data
            series_data = item['series']
            title = series_data.get('title', 'Unknown Series')
            description = series_data.get('longDescription', series_data.get('description', ''))
            content_id = str(series_data.get('seriesId', ''))
        else:
            # For other types, use item data directly
            title = (item.get('title', '') or
                    item.get('name', '') or
                    item.get('seriesTitle', '') or
                    'Unknown Title')

            description = (item.get('description', '') or
                          item.get('longDescription', '') or
                          item.get('shortDescription', ''))

            content_id = str(item.get('id', '') or
                            item.get('seriesId', '') or
                            item.get('contentId', '') or
                            item.get('externalId', ''))

        # Get thumbnail from multiple possible sources
        thumbnail = ''
        if 'thumbnails' in item and item['thumbnails']:
            # Handle both array of URLs and array of objects
            first_thumb = item['thumbnails'][0]
            if isinstance(first_thumb, str):
                thumbnail = first_thumb
            elif isinstance(first_thumb, dict):
                thumbnail = first_thumb.get('source', first_thumb.get('url', ''))
        elif 'smallCoverUrl' in item:
            thumbnail = item['smallCoverUrl']
        elif 'coverUrl' in item:
            thumbnail = item['coverUrl']
        elif 'poster' in item:
            thumbnail = item['poster']

        # Debug logging for troubleshooting
        xbmc.log(f"HIDIVE DEBUG: Processing item - type: {item_type}, title: {title}, id: {content_id}",
                level=xbmc.LOGINFO)

        # Handle different content types
        if item_type in ['SERIES', 'VOD_SERIES', 'VOD_SEASON', 'SHOW']:
            # Handle series/seasons in watchlist - navigate to series seasons
            url = build_url(base_url, 'list_series_seasons', series_id=content_id)
            list_item = create_list_item(
                title,
                art={'thumb': thumbnail, 'poster': thumbnail},
                info={'plot': description, 'mediatype': 'tvshow'}
            )
            return (url, list_item, True)
        elif item_type in ['PLAYLIST', 'VOD_PLAYLIST']:
            # Handle playlist in watchlist
            url = build_url(base_url, 'list_playlist', playlist_id=content_id)
            list_item = create_list_item(
                title,
                art={'thumb': thumbnail, 'poster': thumbnail},
                info={'plot': description, 'mediatype': 'set'}
            )
            return (url, list_item, True)
        else:
            # Default to series handling for unknown types
            xbmc.log(f"HIDIVE DEBUG: Unknown item type '{item_type}', defaulting to series",
                    level=xbmc.LOGINFO)
            url = build_url(base_url, 'list_series_seasons', series_id=content_id)
            list_item = create_list_item(
                title,
                art={'thumb': thumbnail, 'poster': thumbnail},
                info={'plot': description, 'mediatype': 'tvshow'}
            )
            return (url, list_item, True)

    except Exception as e:
        xbmc.log(f"HIDIVE: Error processing watchlist item: {e}", level=xbmc.LOGERROR)
        xbmc.log(f"HIDIVE DEBUG: Item data: {item}", level=xbmc.LOGERROR)
        return None


def handle_series_seasons(api: HidiveAPI, config: AppConfig, series_id: str) -> None:
    """
    Handler for series seasons listing using functional approach.

    Args:
        api: HiDive API instance
        config: Application configuration
        series_id: ID of the series to list seasons for
    """
    # Get series data
    series_result = safe_api_call(api.get_series, series_id)
    if not series_result.is_ok() or not series_result.data.get('seasons'):
        end_directory(config.addon_handle)
        return

    series_data = series_result.data
    series_title = series_data.get('title', 'Seasons')
    fanart_url = series_data.get('keyArtUrl', ADDON.getAddonInfo('fanart'))

    set_plugin_category(config.addon_handle, series_title)

    # Transform season data
    season_data = transform_season_data(series_data['seasons'])
    if season_data:
        season_items = build_season_items(season_data, config.base_url, fanart_url)
        add_directory_items(config.addon_handle, season_items)

    end_directory(config.addon_handle)


def handle_playlist_content(api: HidiveAPI, config: AppConfig, playlist_id: str) -> None:
    """
    Handler for playlist content listing.

    Args:
        api: HiDive API instance
        config: Application configuration
        playlist_id: ID of the playlist to list content for
    """
    # Get playlist data
    playlist_result = safe_api_call(api.get_playlist, playlist_id)
    if not playlist_result.is_ok():
        xbmc.log(f"HIDIVE: Failed to get playlist {playlist_id}", level=xbmc.LOGERROR)
        end_directory(config.addon_handle)
        return

    playlist_data = playlist_result.data
    playlist_title = playlist_data.get('title', 'Playlist')
    fanart_url = playlist_data.get('keyArtUrl', ADDON.getAddonInfo('fanart'))

    set_plugin_category(config.addon_handle, playlist_title)

    # Get content from playlist - HiDive playlists use 'vods' field
    content_items = playlist_data.get('vods', playlist_data.get('contentList', playlist_data.get('episodes', [])))

    # Debug logging for playlist structure
    xbmc.log(f"HIDIVE: Playlist {playlist_id} structure - available keys: {list(playlist_data.keys())}", level=xbmc.LOGINFO)
    if 'vods' in playlist_data:
        xbmc.log(f"HIDIVE: Found {len(playlist_data['vods'])} items in 'vods' field", level=xbmc.LOGINFO)

    if not content_items:
        xbmc.log(f"HIDIVE: No content found in playlist {playlist_id}", level=xbmc.LOGINFO)
        end_directory(config.addon_handle)
        return

    xbmc.log(f"HIDIVE: Found {len(content_items)} items in playlist {playlist_id}", level=xbmc.LOGINFO)

    # Process and display content items
    _process_bucket_content(content_items, config)

    end_directory(config.addon_handle)


def handle_season_episodes(api: HidiveAPI, config: AppConfig, season_id: str) -> None:
    """
    Handler for season episodes listing using functional approach.

    Args:
        api: HiDive API instance
        config: Application configuration
        season_id: ID of the season to list episodes for
    """
    # Get season data
    season_result = safe_api_call(api.get_season, season_id)
    if not season_result.is_ok() or not season_result.data.get('episodes'):
        end_directory(config.addon_handle)
        return

    season_data = season_result.data
    series_title = season_data.get('series', {}).get('title', 'Episodes')
    fanart_url = season_data.get('series', {}).get('keyArtUrl', ADDON.getAddonInfo('fanart'))

    set_plugin_category(config.addon_handle, series_title)

    # Transform episode data
    episode_data = transform_episode_data(season_data['episodes'], series_title)
    if episode_data:
        episode_items = build_episode_items(episode_data, config.base_url, fanart_url)
        add_directory_items(config.addon_handle, episode_items)

    end_directory(config.addon_handle)


def handle_video_playback(api: HidiveAPI, config: AppConfig, video_id: str,
                         available_langs_str: Optional[str]) -> None:
    """
    Handler for video playback using functional approach.

    Args:
        api: HiDive API instance
        config: Application configuration
        video_id: ID of the video to play
        available_langs_str: Comma-separated string of available languages
    """
    # Get language configuration
    lang_config = get_language_config()

    # Parse available languages
    available_langs = parse_available_languages(available_langs_str)

    # Check for audio fallback
    is_fallback_triggered = False
    if config.subtitle_fallback:
        is_fallback_triggered = check_audio_fallback(
            config.preferred_audio_language,
            available_langs,
            lang_config.audio_lang_map
        )
        if is_fallback_triggered:
            log_info("Audio fallback detected. Forcing subtitles.")
            log_debug(f"Fallback triggered: preferred={config.preferred_audio_language}, available={available_langs}", config.enable_debug_logging)

    # Get video stream data
    language_code = lang_config.audio_lang_map.get(config.preferred_audio_language, 'eng')
    playback_result = _get_playback_data(api, video_id, language_code)

    if not playback_result.is_ok():
        show_error_dialog("Playback Failed", playback_result.error)
        resolve_playback(config.addon_handle, False)
        return

    stream_data = playback_result.data

    # Check InputStream availability
    if not check_inputstream_availability():
        show_error_dialog("Playback Failed", "InputStream Adaptive is not installed or configured correctly.")
        resolve_playback(config.addon_handle, False)
        return

    # Create play item
    play_item_result = _create_playback_item(stream_data, config, lang_config, is_fallback_triggered, video_id)
    if not play_item_result.is_ok():
        show_error_dialog("Playback Failed", play_item_result.error)
        resolve_playback(config.addon_handle, False)
        return

    # Resolve playback
    resolve_playback(config.addon_handle, True, play_item_result.data)


def handle_search(api: HidiveAPI, config: AppConfig, query: Optional[str] = None) -> None:
    """
    Handler for search functionality using functional approach.

    Args:
        api: HiDive API instance
        config: Application configuration
        query: Search query string (if None, prompts user for input)
    """
    import xbmc

    set_plugin_category(config.addon_handle, 'Search')

    # If no query provided, prompt user for input
    if not query:
        keyboard = xbmc.Keyboard('', 'Search HiDive')
        keyboard.doModal()
        if not keyboard.isConfirmed():
            return
        query = keyboard.getText()

    if not query or not query.strip():
        return

    # Perform search
    search_result = safe_api_call(api.search, query.strip())
    if not search_result.is_ok():
        show_notification("Search failed", "Could not perform search")
        return

    search_data = search_result.data
    if not search_data or 'results' not in search_data:
        show_notification("No results", f"No results found for '{query}'")
        return

    # Process search results
    search_items = []
    total_results = 0

    for result_set in search_data.get('results', []):
        hits = result_set.get('hits', [])
        total_results += len(hits)

        for hit in hits:
            item_tuple = process_search_hit(api, config, hit)
            if item_tuple:
                search_items.append(item_tuple)

    if total_results == 0:
        show_notification("No results", f"No results found for '{query}'")
    else:
        add_directory_items(config.addon_handle, search_items)

    end_directory(config.addon_handle)


def process_search_hit(api: HidiveAPI, config: AppConfig, hit: Dict[str, Any]) -> Optional[tuple]:
    """
    Process a single search result hit and return a directory item tuple.

    Args:
        api: HiDive API instance
        config: Application configuration
        hit: Search hit data

    Returns:
        Optional[tuple]: (url, list_item, is_folder) tuple or None if processing fails
    """
    try:
        hit_type = hit.get('type', '')
        title = hit.get('name', hit.get('title', 'Unknown Title'))
        description = hit.get('description', '')
        thumbnail = hit.get('coverUrl', hit.get('smallCoverUrl', ''))
        content_id = str(hit.get('id', ''))

        if hit_type == 'VOD_SERIES':
            # Handle series result
            url = build_url(config.base_url, 'list_series_seasons', series_id=content_id)
            list_item = create_list_item(
                title,
                art={'thumb': thumbnail, 'poster': thumbnail},
                info={'plot': description, 'mediatype': 'tvshow'}
            )
            return (url, list_item, True)
        elif hit_type == 'VOD_PLAYLIST':
            # Handle playlist result
            url = build_url(config.base_url, 'list_playlist', playlist_id=content_id)
            list_item = create_list_item(
                title,
                art={'thumb': thumbnail, 'poster': thumbnail},
                info={'plot': description, 'mediatype': 'set'}
            )
            return (url, list_item, True)
    except Exception as e:
        xbmc.log(f"HIDIVE: Error processing search hit: {e}", level=xbmc.LOGERROR)

    return None


def extract_content_from_bucket_data(bucket_data: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    """
    Extract content items from enhanced bucket data response.

    Args:
        bucket_data: Bucket data from API response

    Returns:
        Optional[List[Dict[str, Any]]]: List of content items or None
    """
    if not bucket_data:
        return None

    content_list = bucket_data.get('contentList', [])
    if not content_list:
        return None

    return content_list


def find_bucket_by_name(dashboard_data: Dict[str, Any], bucket_name: str) -> Optional[Dict[str, Any]]:
    """
    Find a bucket by name in dashboard data.

    Args:
        dashboard_data: Dashboard response data
        bucket_name: Name of bucket to find

    Returns:
        Optional[Dict[str, Any]]: Bucket data or None if not found
    """
    if not dashboard_data or 'buckets' not in dashboard_data:
        return None

    for bucket in dashboard_data.get('buckets', []):
        if bucket.get('name', '').lower() == bucket_name.lower():
            return bucket

    return None


# ============================================================================
# ROUTING AND SESSION MANAGEMENT
# ============================================================================

def router(argv):
    """
    Main router function using functional programming principles.
    Separates parsing, configuration, and routing logic.
    """
    # Parse arguments (pure function)
    base_url = argv[0]
    addon_handle = int(argv[1])
    args = parse_qs(argv[2][1:])
    mode = args.get('mode', [None])[0]

    # Create immutable configuration
    config = create_config(ADDON, addon_handle, base_url)

    # Create API instance with debug setting
    api = HidiveAPI(config.username, config.password, config.enable_debug_logging)

    # Route to appropriate handler
    route_request(api, config, mode, args)


def route_request(api: HidiveAPI, config: AppConfig, mode: Optional[str], args: Dict[str, List[str]]):
    """
    Pure routing function that delegates to appropriate handlers.

    Args:
        api: HiDive API instance
        config: Application configuration
        mode: Request mode
        args: URL arguments
    """
    # Handle logout separately (no session required)
    if mode == 'logout':
        handle_logout()
        return

    # Ensure session is valid for all other operations
    session_result = ensure_valid_session(api, config)
    if not session_result.is_ok():
        return

    # Route to specific handlers
    if mode is None:
        handle_main_menu(api, config)
    elif mode == 'profiles':
        handle_profile_selection(api, config)
    elif mode == 'search':
        query = args.get('query', [None])[0]
        handle_search(api, config, query)
    elif mode == 'dashboard':
        handle_dashboard_menu(api, config)
    elif mode == 'watchlists':
        handle_watchlists(api, config)
    elif mode == 'list_watchlist_content':
        watchlist_id = args.get('watchlist_id', [None])[0]
        if watchlist_id:
            handle_watchlist_content(api, config, watchlist_id)
    elif mode == 'list_bucket':
        bucket_name = args.get('name', [None])[0]
        bucket_type = args.get('type', [None])[0]
        bucket_exid = args.get('exid', [None])[0]
        if bucket_name:
            # Use enhanced bucket listing if enabled and metadata is available
            if (config.enable_enhanced_bucket_loading and bucket_type and bucket_exid):
                handle_enhanced_bucket_listing(api, config, bucket_name, bucket_type, bucket_exid)
            else:
                handle_bucket_listing(api, config, bucket_name)
    elif mode == 'list_series_seasons':
        series_id = args.get('series_id', [None])[0]
        if series_id:
            handle_series_seasons(api, config, series_id)
    elif mode == 'list_playlist':
        playlist_id = args.get('playlist_id', [None])[0]
        if playlist_id:
            handle_playlist_content(api, config, playlist_id)
    elif mode == 'list_season_episodes':
        season_id = args.get('season_id', [None])[0]
        if season_id:
            handle_season_episodes(api, config, season_id)
    elif mode == 'play':
        video_id = args.get('video_id', [None])[0]
        langs = args.get('langs', [None])[0]
        if video_id:
            handle_video_playback(api, config, video_id, langs)

# ============================================================================
# SESSION MANAGEMENT
# ============================================================================

def ensure_valid_session(api: HidiveAPI, config: AppConfig) -> Result:
    """
    Functional session validation with clear error handling.

    Args:
        api: HiDive API instance
        config: Application configuration

    Returns:
        Result: Success/failure result
    """
    # Check credentials first
    if not has_credentials(config):
        open_addon_settings(ADDON)
        return Result.error("No credentials provided")

    # Try existing auth token
    if has_auth_token(config):
        api.set_auth_token(config.auth_token)
        profiles_result = safe_api_call(api.get_profiles)
        if profiles_result.is_ok():
            return Result.ok()

    # Clear invalid token and try login
    api.clear_auth_token()
    login_result = safe_api_call(api.login)
    if not login_result.is_ok():
        show_error_dialog("Login Failed", "Please check your credentials.")
        open_addon_settings(ADDON)
        return Result.error("Login failed")

    # Try to activate existing profile
    if has_active_profile(config):
        token_result = safe_api_call(api.activate_profile, config.active_profile_id)
        if token_result.is_ok() and token_result.data:
            update_auth_settings(ADDON, token_result.data, config.active_profile_id)
            api.set_auth_token(token_result.data)
            return Result.ok()
        else:
            # Clear invalid profile
            update_auth_settings(ADDON, '', '')

    # Need profile selection
    return handle_profile_selection_flow(api)

def handle_profile_selection_flow(api: HidiveAPI) -> Result:
    """
    Functional profile selection flow.

    Args:
        api: HiDive API instance

    Returns:
        Result: Success/failure result
    """
    # Ensure authentication
    if not api.is_authenticated():
        login_result = safe_api_call(api.login)
        if not login_result.is_ok():
            show_error_dialog("Login Failed", "Please check your credentials.")
            return Result.error("Login failed")

    # Get profiles
    profiles_result = safe_api_call(api.get_profiles)
    if not profiles_result.is_ok():
        show_error_dialog("Profile Error", "Could not retrieve user profiles.")
        return Result.error("Failed to get profiles")

    # Transform profile data
    profiles_data = extract_profiles_data(profiles_result.data)
    if not profiles_data:
        return Result.error("No profiles available")

    profile_names = [p['name'] for p in profiles_data]

    # Find current profile for preselection
    current_profile_id = ADDON.getSetting('active_profile_id')
    preselect = find_profile_index(profiles_data, current_profile_id)

    # Show selection dialog
    selected_index = show_profile_selection_dialog(profile_names, preselect)
    if selected_index == -1:
        return Result.error("Profile selection cancelled")

    # Activate selected profile
    selected_profile = profiles_data[selected_index]
    profile_id = selected_profile['id']

    token_result = safe_api_call(api.activate_profile, profile_id)
    if token_result.is_ok() and token_result.data:
        update_auth_settings(ADDON, token_result.data, profile_id)
        api.set_auth_token(token_result.data)
        return Result.ok()
    else:
        show_error_dialog("Profile Activation Failed", "Could not activate the selected profile.")
        return Result.error("Profile activation failed")



# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _process_bucket_content(content_items: List[Dict[str, Any]], config: AppConfig) -> None:
    """
    Private function to process and display bucket content items.

    Args:
        content_items: List of content items from bucket
        config: Application configuration
    """
    series_items = []
    video_items = []

    # Separate series and video items with debug logging
    content_type_counts = {}
    unhandled_types = set()

    for item in content_items:
        item_type = item.get('type', '').lower()
        content_type_counts[item_type] = content_type_counts.get(item_type, 0) + 1

        if item_type in ['vod_series', 'vod_season']:
            series_data = transform_series_item(item, item_type)
            if series_data:
                # Add fallback fanart
                if not series_data['art'].get('fanart'):
                    series_data['art']['fanart'] = ADDON.getAddonInfo('fanart')
                series_items.append(series_data)

        elif item_type in ['vod', 'movie', 'vod_movie']:  # Added movie types
            video_data = transform_video_item(item)
            if video_data:
                # Add fallback fanart
                if not video_data['art'].get('fanart'):
                    video_data['art']['fanart'] = ADDON.getAddonInfo('fanart')
                video_items.append(video_data)

        elif item_type in ['playlist']:  # Handle playlist content (like Movies bucket)
            # Playlists should be treated as series/collections
            series_data = transform_series_item(item, item_type)
            if series_data:
                # Add fallback fanart
                if not series_data['art'].get('fanart'):
                    series_data['art']['fanart'] = ADDON.getAddonInfo('fanart')
                series_items.append(series_data)

        else:
            # Track unhandled content types for debugging
            unhandled_types.add(item_type)

    # Debug logging for content types
    xbmc.log(f"HIDIVE: Content type distribution: {content_type_counts}", level=xbmc.LOGINFO)
    if unhandled_types:
        xbmc.log(f"HIDIVE: Unhandled content types: {list(unhandled_types)}", level=xbmc.LOGWARNING)

    # Build and add directory items
    if series_items:
        series_dir_items = build_series_items(series_items, config.base_url)
        add_directory_items(config.addon_handle, series_dir_items)

    if video_items:
        video_dir_items = build_video_items(video_items, config.base_url)
        add_directory_items(config.addon_handle, video_dir_items)



def _get_playback_data(api: HidiveAPI, video_id: str, language_code: str) -> Result:
    """
    Private function to get video playback data.

    Args:
        api: HiDive API instance
        video_id: ID of the video
        language_code: Language code for audio

    Returns:
        Result: Stream data or error
    """
    # Get video metadata
    video_result = safe_api_call(api.get_video_data, video_id, language=language_code)
    if not video_result.is_ok():
        return Result.error("Could not get video metadata.")

    video_data = video_result.data
    if not video_data.get('playerUrlCallback'):
        return Result.error("Could not get video metadata.")

    # Get stream data
    stream_result = safe_api_call(api.get_stream_from_callback, video_data['playerUrlCallback'])
    if not stream_result.is_ok():
        return Result.error("Could not get stream information.")

    # Extract Widevine stream
    widevine_stream = extract_widevine_stream(stream_result.data)
    if not widevine_stream:
        return Result.error("No suitable (Widevine) stream found.")

    return Result.ok(widevine_stream)


def _create_playback_item(stream_data: Dict[str, Any], config: AppConfig,
                         lang_config: LanguageConfig, is_fallback_triggered: bool, video_id: str) -> Result:
    """
    Private function to create a playback item.

    Args:
        stream_data: Stream data from API
        config: Application configuration
        lang_config: Language configuration
        is_fallback_triggered: Whether subtitle fallback was triggered
        video_id: Video ID for subtitle caching

    Returns:
        Result: Play item or error
    """
    # Prepare subtitles if needed
    subtitles = []
    if should_enable_subtitles(config.enable_subtitles, is_fallback_triggered):
        if 'subtitles' in stream_data:
            # Debug log subtitle metadata from API
            log_debug(f"Raw subtitle data from API: {stream_data['subtitles']}", config.enable_debug_logging)

            preferred_sub_lang = lang_config.subtitle_lang_map.get(config.preferred_subtitle_language)
            log_debug(f"Preferred subtitle language: {preferred_sub_lang}", config.enable_debug_logging)

            # Use new subtitle processing system that converts SRT to ASS and caches locally
            log_debug("Using SRT-to-ASS conversion with local caching", config.enable_debug_logging)
            log_debug(f"Subtitle positioning: base_margin={config.subtitle_base_margin}, vertical_spacing={config.subtitle_vertical_spacing}", config.enable_debug_logging)

            # Log cache info for debugging
            if config.enable_debug_logging:
                cache_info = get_cache_info()
                log_debug(f"Cache info: {cache_info}", True)
            subtitles = process_subtitle_list(
                stream_data['subtitles'],
                preferred_sub_lang,
                video_id,
                config.subtitle_base_margin,
                config.subtitle_vertical_spacing,
                config.enable_debug_logging,
                config.subtitle_font_name,
                config.subtitle_font_size,
                config.subtitle_primary_color,
                config.subtitle_outline_color,
                config.subtitle_back_color,
                config.subtitle_bold,
                config.subtitle_italic,
                config.subtitle_outline_width,
                config.subtitle_shadow_depth
            )

            # Debug log final subtitle file paths being passed to Kodi
            log_debug(f"Final cached ASS subtitle files for Kodi: {subtitles}", config.enable_debug_logging)

            # Additional validation for debugging
            if config.enable_debug_logging and subtitles:
                import xbmcvfs
                for i, subtitle_path in enumerate(subtitles):
                    if xbmcvfs.exists(subtitle_path):
                        # Convert to filesystem path to get size
                        fs_path = xbmcvfs.translatePath(subtitle_path)
                        try:
                            file_size = os.path.getsize(fs_path)
                            log_debug(f"Subtitle file {i+1} exists: {subtitle_path} ({file_size} bytes)", True)
                        except:
                            log_debug(f"Subtitle file {i+1} exists: {subtitle_path} (size unknown)", True)
                    else:
                        log_error(f"Subtitle file {i+1} MISSING: {subtitle_path}")

            # Clean up old cache files periodically
            if subtitles:
                cleanup_old_cache_files()

    # Create play item
    license_data = stream_data.get('drm')
    play_item = create_play_item(stream_data['url'], license_data, subtitles)

    return Result.ok(play_item)


if __name__ == '__main__':
    router(sys.argv)