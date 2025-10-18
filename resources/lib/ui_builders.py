# -*- coding: utf-8 -*-
"""
UI building functions for Kodi interface.
These functions handle the creation of Kodi list items and directory structures.
"""

from typing import List, Dict, Any, Optional
import xbmcgui
import xbmcplugin
from data_transforms import filter_art_dict, build_url


def create_list_item(title: str, art: Optional[Dict[str, str]] = None, 
                    info: Optional[Dict[str, Any]] = None, 
                    is_playable: bool = False) -> xbmcgui.ListItem:
    """
    Pure function to create a Kodi ListItem with given properties.
    
    Args:
        title: Item title
        art: Dictionary of art URLs
        info: Video info dictionary
        is_playable: Whether the item is playable
        
    Returns:
        xbmcgui.ListItem: Configured list item
    """
    list_item = xbmcgui.ListItem(label=title)
    
    if is_playable:
        list_item.setProperty('IsPlayable', 'true')
    
    if art:
        filtered_art = filter_art_dict(art)
        if filtered_art:
            list_item.setArt(filtered_art)
    
    if info:
        list_item.setInfo('video', info)
    
    return list_item


def build_main_menu_items(bucket_names: List[str], base_url: str) -> List[tuple]:
    """
    Pure function to build main menu directory items.

    Args:
        bucket_names: List of bucket names to display
        base_url: Base URL for building navigation URLs

    Returns:
        List[tuple]: List of (url, list_item, is_folder) tuples
    """
    items = []

    # 1. Search
    search_item = create_list_item(
        'Search',
        art={'icon': 'DefaultAddonsSearch.png'},
        info={'plot': 'Search HiDive content'}
    )
    search_url = build_url(base_url, 'search')
    items.append((search_url, search_item, True))

    # 2. Dashboard (submenu)
    dashboard_item = create_list_item('Dashboard')
    dashboard_url = build_url(base_url, 'dashboard')
    items.append((dashboard_url, dashboard_item, True))

    # 3. My Watchlists
    watchlists_item = create_list_item('My Watchlists')
    watchlists_url = build_url(base_url, 'watchlists')
    items.append((watchlists_url, watchlists_item, True))

    # 4. Switch Profile
    profile_item = create_list_item('Switch Profile')
    profile_url = build_url(base_url, 'profiles')
    items.append((profile_url, profile_item, True))

    # 5. Logout
    logout_item = create_list_item('Logout')
    logout_url = build_url(base_url, 'logout')
    items.append((logout_url, logout_item, False))

    return items


def build_enhanced_main_menu_items(buckets: List[Dict[str, Any]], base_url: str) -> List[tuple]:
    """
    Enhanced function to build main menu items with new layout.

    Args:
        buckets: List of bucket data with metadata (used for dashboard submenu)
        base_url: Base URL for building navigation URLs

    Returns:
        List[tuple]: List of (url, list_item, is_folder) tuples
    """
    items = []

    # 1. Search
    search_item = create_list_item(
        'Search',
        art={'icon': 'DefaultAddonsSearch.png'},
        info={'plot': 'Search HiDive content'}
    )
    search_url = build_url(base_url, 'search')
    items.append((search_url, search_item, True))

    # 2. Dashboard (submenu)
    dashboard_item = create_list_item('Dashboard')
    dashboard_url = build_url(base_url, 'dashboard')
    items.append((dashboard_url, dashboard_item, True))

    # 3. My Watchlists
    watchlists_item = create_list_item('My Watchlists')
    watchlists_url = build_url(base_url, 'watchlists')
    items.append((watchlists_url, watchlists_item, True))

    # 4. Switch Profile
    profile_item = create_list_item('Switch Profile')
    profile_url = build_url(base_url, 'profiles')
    items.append((profile_url, profile_item, True))

    # 5. Logout
    logout_item = create_list_item('Logout')
    logout_url = build_url(base_url, 'logout')
    items.append((logout_url, logout_item, False))

    return items


def build_dashboard_menu_items(bucket_names: List[str], base_url: str) -> List[tuple]:
    """
    Pure function to build dashboard submenu items.

    Args:
        bucket_names: List of bucket names to display
        base_url: Base URL for building navigation URLs

    Returns:
        List[tuple]: List of (url, list_item, is_folder) tuples
    """
    items = []

    # Add bucket items
    for bucket_name in bucket_names:
        formatted_name = bucket_name.replace('_', ' ').title()
        list_item = create_list_item(formatted_name)
        url = build_url(base_url, 'list_bucket', name=bucket_name)
        items.append((url, list_item, True))

    return items


def build_enhanced_dashboard_menu_items(buckets: List[Dict[str, Any]], base_url: str) -> List[tuple]:
    """
    Enhanced function to build dashboard submenu items with bucket metadata.

    Args:
        buckets: List of bucket data with metadata
        base_url: Base URL for building navigation URLs

    Returns:
        List[tuple]: List of (url, list_item, is_folder) tuples
    """
    items = []

    # Add enhanced bucket items with metadata
    for bucket in buckets:
        bucket_name = bucket.get('name', 'Unknown')
        bucket_type = bucket.get('type', '')
        bucket_exid = bucket.get('exid', '')

        formatted_name = bucket_name.replace('_', ' ').title()
        list_item = create_list_item(formatted_name)

        # Build URL with bucket metadata for enhanced pagination
        if bucket_type and bucket_exid:
            url = build_url(base_url, 'list_bucket',
                          name=bucket_name, type=bucket_type, exid=bucket_exid)
        else:
            url = build_url(base_url, 'list_bucket', name=bucket_name)

        items.append((url, list_item, True))

    return items


def build_series_items(series_data: List[Dict[str, Any]], base_url: str) -> List[tuple]:
    """
    Pure function to build series directory items (including playlists).

    Args:
        series_data: List of transformed series data (including playlists)
        base_url: Base URL for building navigation URLs

    Returns:
        List[tuple]: List of (url, list_item, is_folder) tuples
    """
    items = []

    for series in series_data:
        list_item = create_list_item(
            title=series['title'],
            art=series['art'],
            info={'title': series['title'], 'plot': series['description']}
        )

        # Determine if this is a playlist or series based on the item_type stored during transformation
        # For now, we'll use a simple heuristic - if the item has a 'playlist' flag or specific naming
        item_type = series.get('item_type', 'series')

        if item_type == 'playlist':
            url = build_url(base_url, 'list_playlist', playlist_id=series['id'])
        else:
            url = build_url(base_url, 'list_series_seasons', series_id=series['id'])

        items.append((url, list_item, True))

    return items


def build_video_items(video_data: List[Dict[str, Any]], base_url: str) -> List[tuple]:
    """
    Pure function to build video directory items.
    
    Args:
        video_data: List of transformed video data
        base_url: Base URL for building navigation URLs
        
    Returns:
        List[tuple]: List of (url, list_item, is_folder) tuples
    """
    items = []
    
    for video in video_data:
        list_item = create_list_item(
            title=video['title'],
            art=video['art'],
            info={'title': video['title'], 'plot': video['description']},
            is_playable=True
        )
        url = build_url(base_url, 'play', video_id=video['id'], langs='')
        items.append((url, list_item, False))
    
    return items


def build_season_items(season_data: List[Dict[str, Any]], base_url: str, 
                      fanart_url: Optional[str] = None) -> List[tuple]:
    """
    Pure function to build season directory items.
    
    Args:
        season_data: List of transformed season data
        base_url: Base URL for building navigation URLs
        fanart_url: Optional fanart URL to use as fallback
        
    Returns:
        List[tuple]: List of (url, list_item, is_folder) tuples
    """
    items = []
    
    for season in season_data:
        # Add fanart fallback if not present
        art = season['art'].copy()
        if fanart_url and not art.get('fanart'):
            art['fanart'] = fanart_url
        
        list_item = create_list_item(
            title=season['title'],
            art=art,
            info={'title': season['title']}
        )
        url = build_url(base_url, 'list_season_episodes', season_id=season['id'])
        items.append((url, list_item, True))
    
    return items


def build_episode_items(episode_data: List[Dict[str, Any]], base_url: str,
                       fanart_url: Optional[str] = None) -> List[tuple]:
    """
    Pure function to build episode directory items.
    
    Args:
        episode_data: List of transformed episode data
        base_url: Base URL for building navigation URLs
        fanart_url: Optional fanart URL to use as fallback
        
    Returns:
        List[tuple]: List of (url, list_item, is_folder) tuples
    """
    items = []
    
    for episode in episode_data:
        # Add fanart fallback if not present
        art = episode['art'].copy()
        if fanart_url and not art.get('fanart'):
            art['fanart'] = fanart_url
        
        info = {
            'title': episode['title'],
            'plot': episode['description'],
            'tvshowtitle': episode['series_title'],
            'season': episode['season_number'],
            'episode': episode['episode_number']
        }
        
        list_item = create_list_item(
            title=episode['title'],
            art=art,
            info=info,
            is_playable=True
        )
        
        langs_str = ','.join(episode['available_languages'])
        url = build_url(base_url, 'play', video_id=episode['id'], langs=langs_str)
        items.append((url, list_item, False))
    
    return items


def add_directory_items(handle: int, items: List[tuple]) -> None:
    """
    Side effect function to add directory items to Kodi.
    
    Args:
        handle: Kodi addon handle
        items: List of (url, list_item, is_folder) tuples
    """
    for url, list_item, is_folder in items:
        xbmcplugin.addDirectoryItem(handle, url, list_item, isFolder=is_folder)


def set_plugin_category(handle: int, category: str) -> None:
    """
    Side effect function to set the plugin category.
    
    Args:
        handle: Kodi addon handle
        category: Category name to display
    """
    xbmcplugin.setPluginCategory(handle, category)


def end_directory(handle: int) -> None:
    """
    Side effect function to end the directory listing.
    
    Args:
        handle: Kodi addon handle
    """
    xbmcplugin.endOfDirectory(handle)


def show_error_dialog(title: str, message: str) -> None:
    """
    Side effect function to show an error dialog.
    
    Args:
        title: Dialog title
        message: Error message to display
    """
    dialog = xbmcgui.Dialog()
    dialog.ok(title, message)


def show_profile_selection_dialog(profile_names: List[str], 
                                 preselect: int = -1) -> int:
    """
    Side effect function to show profile selection dialog.
    
    Args:
        profile_names: List of profile names to display
        preselect: Index of profile to preselect
        
    Returns:
        int: Selected profile index, or -1 if cancelled
    """
    dialog = xbmcgui.Dialog()
    return dialog.select("Select Profile", profile_names, preselect=preselect)
