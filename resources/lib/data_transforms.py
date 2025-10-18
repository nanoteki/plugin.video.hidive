# -*- coding: utf-8 -*-
"""
Pure data transformation functions for HiDive content.
"""

from typing import List, Dict, Any, Optional, Tuple
try:
    from urllib import quote
except ImportError:
    from urllib.parse import quote

def extract_bucket_names(dashboard_data: Optional[Dict[str, Any]]) -> List[str]:
    """
    Pure function to extract bucket names from dashboard data.

    Args:
        dashboard_data: Dashboard API response data

    Returns:
        List[str]: List of bucket names
    """
    if not dashboard_data or not dashboard_data.get('buckets'):
        return []

    # Extract all bucket names and add debug logging
    all_buckets = [
        bucket.get('name')
        for bucket in dashboard_data.get('buckets', [])
        if bucket.get('name')
    ]

    # Debug logging to help identify missing buckets
    try:
        import xbmc
        xbmc.log(f"HIDIVE: Available buckets from API: {all_buckets}", level=xbmc.LOGINFO)

        # Also log bucket details for debugging
        for bucket in dashboard_data.get('buckets', []):
            bucket_name = bucket.get('name', 'Unknown')
            content_count = len(bucket.get('contentList', []))
            bucket_type = bucket.get('type', 'Unknown')
            xbmc.log(f"HIDIVE: Bucket '{bucket_name}' - Type: {bucket_type}, Content count: {content_count}",
                    level=xbmc.LOGINFO)
    except ImportError:
        # Handle case where xbmc module is not available (e.g., during testing)
        pass

    return all_buckets


def format_bucket_name(bucket_name: str) -> str:
    """
    Pure function to format bucket name for display.
    
    Args:
        bucket_name: Raw bucket name
        
    Returns:
        str: Formatted bucket name
    """
    return bucket_name.replace('_', ' ').title()


def extract_profiles_data(profiles_response: Optional[List[Dict[str, Any]]]) -> List[Dict[str, str]]:
    """
    Pure function to extract and normalize profile data.
    
    Args:
        profiles_response: Profiles API response data
        
    Returns:
        List[Dict[str, str]]: Normalized profile data
    """
    if not profiles_response:
        return []
    
    return [
        {
            'id': profile.get('profileId', ''),
            'name': profile.get('displayName', 'Unknown Profile')
        }
        for profile in profiles_response
    ]


def find_profile_index(profiles: List[Dict[str, str]], profile_id: str) -> int:
    """
    Pure function to find the index of a profile by ID.
    
    Args:
        profiles: List of profile dictionaries
        profile_id: Profile ID to find
        
    Returns:
        int: Index of profile, or -1 if not found
    """
    for i, profile in enumerate(profiles):
        if profile.get('id') == profile_id:
            return i
    return -1


def extract_content_from_bucket(dashboard_data: Optional[Dict[str, Any]],
                               bucket_name: str) -> List[Dict[str, Any]]:
    """
    Pure function to extract content items from a specific bucket.

    Args:
        dashboard_data: Dashboard API response data
        bucket_name: Name of the bucket to extract content from

    Returns:
        List[Dict[str, Any]]: List of content items
    """
    if not dashboard_data or not dashboard_data.get('buckets'):
        try:
            import xbmc
            xbmc.log(f"HIDIVE: No dashboard data or buckets available for bucket '{bucket_name}'",
                    level=xbmc.LOGWARNING)
        except ImportError:
            pass
        return []

    # Debug logging for bucket search
    try:
        import xbmc
        available_bucket_names = [b.get('name', 'Unknown') for b in dashboard_data.get('buckets', [])]
        xbmc.log(f"HIDIVE: Looking for bucket '{bucket_name}' in available buckets: {available_bucket_names}",
                level=xbmc.LOGINFO)
    except ImportError:
        pass

    for bucket in dashboard_data['buckets']:
        if bucket.get('name', '').lower() == bucket_name.lower():
            content_list = bucket.get('contentList', [])

            # Debug logging for found bucket
            try:
                import xbmc
                xbmc.log(f"HIDIVE: Found bucket '{bucket_name}' with {len(content_list)} items",
                        level=xbmc.LOGINFO)

                # Log content types for debugging
                if content_list:
                    content_types = {}
                    for item in content_list[:5]:  # Log first 5 items
                        item_type = item.get('type', 'Unknown')
                        content_types[item_type] = content_types.get(item_type, 0) + 1
                        xbmc.log(f"HIDIVE: Sample item in '{bucket_name}': type='{item_type}', title='{item.get('title', 'Unknown')}'",
                                level=xbmc.LOGINFO)

                    xbmc.log(f"HIDIVE: Content types in '{bucket_name}': {content_types}",
                            level=xbmc.LOGINFO)
            except ImportError:
                pass

            return content_list

    # Debug logging for bucket not found
    try:
        import xbmc
        xbmc.log(f"HIDIVE: Bucket '{bucket_name}' not found in dashboard data",
                level=xbmc.LOGWARNING)
    except ImportError:
        pass

    return []


def transform_series_item(item: Dict[str, Any], item_type: str) -> Optional[Dict[str, Any]]:
    """
    Pure function to transform a series item for UI display.

    Args:
        item: Raw content item data
        item_type: Type of the content item

    Returns:
        Optional[Dict[str, Any]]: Transformed item data or None if invalid
    """
    if item_type not in ['vod_series', 'vod_season', 'playlist']:
        return None

    # Handle playlist items (like Movies bucket content)
    if item_type == 'playlist':
        playlist_id = item.get('id')
        if not playlist_id:
            return None

        return {
            'id': playlist_id,
            'title': item.get('title', 'Unknown Playlist'),
            'description': item.get('description', ''),
            'item_type': 'playlist',  # Add item type for routing
            'art': {
                'thumb': item.get('posterUrl'),
                'poster': item.get('posterUrl'),
                'fanart': item.get('keyArtUrl'),
                'banner': item.get('coverUrl')
            }
        }

    # Handle series and season items
    series_info = item if item_type == 'vod_series' else item.get('series', {})
    series_id = series_info.get('seriesId')

    if not series_id:
        return None

    return {
        'id': series_id,
        'title': series_info.get('title', 'Unknown Series'),
        'description': series_info.get('description', ''),
        'item_type': 'series',  # Add item type for routing
        'art': {
            'thumb': item.get('posterUrl', series_info.get('posterUrl')),
            'poster': item.get('posterUrl', series_info.get('posterUrl')),
            'fanart': item.get('keyArtUrl', series_info.get('keyArtUrl')),
            'banner': item.get('coverUrl', series_info.get('coverUrl'))
        }
    }


def transform_video_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Pure function to transform a video item for UI display.
    
    Args:
        item: Raw video item data
        
    Returns:
        Optional[Dict[str, Any]]: Transformed item data or None if invalid
    """
    video_id = item.get('id')
    if not video_id:
        return None
    
    return {
        'id': video_id,
        'title': item.get('title', 'Unknown Video'),
        'description': item.get('description', ''),
        'art': {
            'thumb': item.get('coverUrl'),
            'poster': item.get('posterUrl'),
            'fanart': item.get('keyArtUrl'),
            'banner': item.get('coverUrl')
        }
    }


def transform_season_data(seasons: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Pure function to transform season data for UI display.
    
    Args:
        seasons: List of raw season data
        
    Returns:
        List[Dict[str, Any]]: List of transformed season data
    """
    transformed_seasons = []
    
    for season in seasons:
        season_id = season.get('id')
        if not season_id:
            continue
        
        season_number = season.get('seasonNumber')
        title = f"Season {season_number}" if season_number else season.get('title', 'Unknown Season')
        
        transformed_seasons.append({
            'id': season_id,
            'title': title,
            'art': {
                'thumb': season.get('posterUrl'),
                'poster': season.get('posterUrl'),
                'banner': season.get('coverUrl')
            }
        })
    
    return transformed_seasons


def transform_episode_data(episodes: List[Dict[str, Any]], 
                          series_title: str = 'Episodes') -> List[Dict[str, Any]]:
    """
    Pure function to transform episode data for UI display.
    
    Args:
        episodes: List of raw episode data
        series_title: Title of the series for context
        
    Returns:
        List[Dict[str, Any]]: List of transformed episode data
    """
    transformed_episodes = []
    
    for episode in episodes:
        video_id = episode.get('id')
        if not video_id:
            continue
        
        episode_info = episode.get('episodeInformation', {})
        available_langs = episode.get('offlinePlaybackLanguages', [])
        
        transformed_episodes.append({
            'id': video_id,
            'title': episode.get('title', 'Unknown Episode'),
            'description': episode.get('description', ''),
            'series_title': series_title,
            'season_number': episode_info.get('seasonNumber'),
            'episode_number': episode_info.get('episodeNumber'),
            'available_languages': available_langs,
            'art': {
                'thumb': episode.get('thumbnailUrl'),
                'poster': episode.get('thumbnailUrl'),
                'banner': episode.get('coverUrl')
            }
        })
    
    return transformed_episodes


def build_url(base_url: str, mode: str, **params) -> str:
    """
    Pure function to build URLs for Kodi navigation.
    
    Args:
        base_url: Base URL for the plugin
        mode: Mode parameter for routing
        **params: Additional URL parameters
        
    Returns:
        str: Complete URL with parameters
    """
    url_params = [f'mode={mode}']
    
    for key, value in params.items():
        if value is not None:
            url_params.append(f'{key}={quote(str(value))}')
    
    return f'{base_url}?{"&".join(url_params)}'


def should_enable_subtitles(config_enable_subtitles: bool, is_fallback_triggered: bool) -> bool:
    """
    Pure function to determine if subtitles should be enabled.
    
    Args:
        config_enable_subtitles: User's subtitle preference
        is_fallback_triggered: Whether audio fallback was triggered
        
    Returns:
        bool: True if subtitles should be enabled
    """
    return config_enable_subtitles or is_fallback_triggered


def check_audio_fallback(preferred_lang: str, available_langs: List[str], 
                        audio_lang_map: Dict[str, str]) -> bool:
    """
    Pure function to check if audio fallback should be triggered.
    
    Args:
        preferred_lang: User's preferred audio language
        available_langs: List of available languages for the content
        audio_lang_map: Mapping of language names to codes
        
    Returns:
        bool: True if fallback should be triggered
    """
    requested_lang_code = audio_lang_map.get(preferred_lang)
    return (requested_lang_code != 'jpn' and 
            requested_lang_code not in available_langs and 
            'jpn' in available_langs)


def filter_art_dict(art_dict: Dict[str, Optional[str]]) -> Dict[str, str]:
    """
    Pure function to filter out None values from art dictionary.
    
    Args:
        art_dict: Dictionary with potential None values
        
    Returns:
        Dict[str, str]: Dictionary with only non-None values
    """
    return {k: v for k, v in art_dict.items() if v}
