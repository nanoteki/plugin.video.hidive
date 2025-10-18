# -*- coding: utf-8 -*-
"""
Utility functions for the HiDive addon.
Contains helper functions and side effect management.
"""

from typing import Optional, Dict, Any, List
import json
import base64
import xbmc
import xbmcgui
import xbmcplugin
from inputstreamhelper import Helper
try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode


def log_info(message: str) -> None:
    """
    Side effect function to log info messages.

    Args:
        message: Message to log
    """
    xbmc.log(f"HIDIVE: {message}", level=xbmc.LOGINFO)


def log_error(message: str) -> None:
    """
    Side effect function to log error messages.

    Args:
        message: Error message to log
    """
    xbmc.log(f"HIDIVE: {message}", level=xbmc.LOGERROR)


def log_debug(message: str, debug_enabled: bool = False) -> None:
    """
    Side effect function to log debug messages conditionally.

    Args:
        message: Debug message to log
        debug_enabled: Whether debug logging is enabled
    """
    if debug_enabled:
        xbmc.log(f"HIDIVE DEBUG: {message}", level=xbmc.LOGINFO)


def show_notification(title: str, message: str, time_ms: int = 5000) -> None:
    """
    Side effect function to show a notification to the user.

    Args:
        title: Notification title
        message: Notification message
        time_ms: Display time in milliseconds (default: 5000)
    """
    xbmcgui.Dialog().notification(title, message, time=time_ms)


def log_api_response(operation: str, response_data: Any, debug_enabled: bool = False) -> None:
    """
    Side effect function to log API response data conditionally.

    Args:
        operation: Name of the API operation
        response_data: Response data from the API
        debug_enabled: Whether debug logging is enabled
    """
    if debug_enabled and response_data is not None:
        # Convert response to string, truncating if too long
        response_str = str(response_data)
        if len(response_str) > 1000:
            response_str = response_str[:1000] + "... [truncated]"
        xbmc.log(f"HIDIVE DEBUG API Response [{operation}]: {response_str}", level=xbmc.LOGINFO)


def log_subtitle_content(subtitle_url: str) -> None:
    """
    Side effect function to fetch and log subtitle file content for debugging.

    Args:
        subtitle_url: URL of the subtitle file to fetch and log
    """
    try:
        import requests
        response = requests.get(subtitle_url, timeout=10)
        response.raise_for_status()

        # Log subtitle file info
        content_type = response.headers.get('content-type', 'unknown')
        content_length = len(response.text)

        log_info(f"Subtitle file info - URL: {subtitle_url}")
        log_info(f"Subtitle file info - Content-Type: {content_type}, Length: {content_length} chars")

        # Log first 500 characters of subtitle content for analysis
        content_preview = response.text[:500]
        if len(response.text) > 500:
            content_preview += "... [truncated]"

        log_info(f"Subtitle content preview:\n{content_preview}")

        # Analyze subtitle format
        content_lower = response.text.lower()
        if content_lower.startswith('[script info]') or 'dialogue:' in content_lower:
            log_info("Subtitle format detected: ASS/SSA (Advanced SubStation Alpha)")
        elif content_lower.startswith('webvtt'):
            log_info("Subtitle format detected: WebVTT")
        elif '-->' in content_lower and content_lower.strip().startswith('1'):
            log_info("Subtitle format detected: SRT (SubRip)")
        else:
            log_info("Subtitle format detected: Unknown/Other")

    except Exception as e:
        log_error(f"Failed to fetch subtitle content from {subtitle_url}: {e}")


def refresh_container() -> None:
    """
    Side effect function to refresh the Kodi container.
    """
    xbmc.executebuiltin('Container.Refresh')


def open_addon_settings(addon) -> None:
    """
    Side effect function to open addon settings.
    
    Args:
        addon: Kodi addon instance
    """
    addon.openSettings()


def create_play_item(stream_url: str, license_data: Optional[Dict[str, Any]] = None,
                    subtitles: Optional[List[str]] = None) -> xbmcgui.ListItem:
    """
    Function to create a playable ListItem for video streaming.
    
    Args:
        stream_url: URL of the video stream
        license_data: Optional DRM license data
        subtitles: Optional list of subtitle URLs
        
    Returns:
        xbmcgui.ListItem: Configured playable item
    """
    play_item = xbmcgui.ListItem(path=stream_url)
    play_item.setProperty('inputstream', 'inputstream.adaptive')
    play_item.setProperty('inputstream.adaptive.manifest_type', 'mpd')
    play_item.setProperty('inputstream.adaptive.max_bandwidth', '99999999')
    
    if subtitles:
        log_debug(f"Setting subtitles on play item: {subtitles}", True)  # Always log this for debugging
        play_item.setSubtitles(subtitles)
        log_debug(f"Subtitles set successfully on play item", True)
    
    if license_data:
        _configure_drm(play_item, license_data)
    
    return play_item


def _configure_drm(play_item: xbmcgui.ListItem, license_data: Dict[str, Any]) -> None:
    """
    Private function to configure DRM for a play item.
    
    Args:
        play_item: ListItem to configure
        license_data: DRM license configuration data
    """
    is_helper = Helper('mpd', drm='com.widevine.alpha')
    if not is_helper.check_inputstream():
        return
    
    play_item.setProperty('inputstream.adaptive.license_type', 'com.widevine.alpha')
    
    license_url = license_data['url']
    jwt_token = license_data['jwtToken']
    
    drm_info = {
        "system": "com.widevine.alpha",
        "key_ids": None
    }
    encoded_drm_info = base64.b64encode(json.dumps(drm_info).encode('utf-8')).decode('utf-8')
    
    headers = urlencode({
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {jwt_token}',
        'X-Drm-Info': encoded_drm_info
    })
    
    license_key = f"{license_url}|{headers}|R{{SSM}}|"
    play_item.setProperty('inputstream.adaptive.license_key', license_key)


def resolve_playback(handle: int, success: bool, play_item: Optional[xbmcgui.ListItem] = None) -> None:
    """
    Side effect function to resolve video playback.
    
    Args:
        handle: Kodi addon handle
        success: Whether playback was successful
        play_item: Optional play item for successful playback
    """
    if success and play_item:
        xbmcplugin.setResolvedUrl(handle, True, listitem=play_item)
    else:
        xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())


def check_inputstream_availability() -> bool:
    """
    Function to check if InputStream Adaptive is available.
    
    Returns:
        bool: True if InputStream Adaptive is available
    """
    is_helper = Helper('mpd', drm='com.widevine.alpha')
    return is_helper.check_inputstream()


def extract_widevine_stream(stream_data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Pure function to extract Widevine-compatible stream from stream data.
    
    Args:
        stream_data: Stream data from API
        
    Returns:
        Optional[Dict[str, Any]]: Widevine stream data or None
    """
    if not stream_data:
        return None
    
    dash_stream = stream_data.get('dash')
    if not dash_stream:
        return None
    
    drm_data = dash_stream.get('drm', {})
    key_systems = drm_data.get('keySystems', [])
    
    if "WIDEVINE" in key_systems:
        return dash_stream
    
    return None


def prepare_subtitle_list(subtitles_data: List[Dict[str, Any]],
                         preferred_lang: str, debug_enabled: bool = False) -> List[str]:
    """
    Pure function to prepare ordered subtitle list based on preference.

    Args:
        subtitles_data: List of subtitle data from API
        preferred_lang: Preferred subtitle language code
        debug_enabled: Whether debug logging is enabled

    Returns:
        List[str]: Ordered list of subtitle URLs
    """
    if not subtitles_data:
        log_debug("No subtitle data provided", debug_enabled)
        return []

    log_debug(f"Processing {len(subtitles_data)} subtitle entries", debug_enabled)

    # Log all available subtitle formats and languages
    for i, sub in enumerate(subtitles_data):
        log_debug(f"Subtitle {i+1}: format={sub.get('format')}, language={sub.get('language')}, url={sub.get('url')}", debug_enabled)

    # Filter for SRT format subtitles
    srt_subs = [s for s in subtitles_data if s.get('format') == 'srt']
    log_debug(f"Found {len(srt_subs)} SRT format subtitles out of {len(subtitles_data)} total", debug_enabled)

    # Separate preferred and other subtitles
    preferred_subs = [s['url'] for s in srt_subs if s.get('language') == preferred_lang]
    other_subs = [s['url'] for s in srt_subs if s.get('language') != preferred_lang]

    log_debug(f"Preferred language '{preferred_lang}' subtitles: {len(preferred_subs)}", debug_enabled)
    log_debug(f"Other language subtitles: {len(other_subs)}", debug_enabled)

    # Return preferred first, then others
    result = preferred_subs + other_subs
    log_debug(f"Final subtitle list order: {result}", debug_enabled)
    return result


def parse_available_languages(langs_str: Optional[str]) -> List[str]:
    """
    Pure function to parse available languages string.
    
    Args:
        langs_str: Comma-separated language string
        
    Returns:
        List[str]: List of language codes
    """
    if not langs_str:
        return []
    return langs_str.split(',')


class Result:
    """
    Simple Result type for functional error handling.
    """
    def __init__(self, success: bool, data: Any = None, error: str = ""):
        self.success = success
        self.data = data
        self.error = error
    
    @classmethod
    def ok(cls, data: Any = None):
        """Create a successful result."""
        return cls(True, data)
    
    @classmethod
    def error(cls, error: str):
        """Create an error result."""
        return cls(False, None, error)
    
    def is_ok(self) -> bool:
        """Check if result is successful."""
        return self.success
    
    def is_error(self) -> bool:
        """Check if result is an error."""
        return not self.success


def safe_api_call(api_func, *args, **kwargs) -> Result:
    """
    Wrapper function for safe API calls with functional error handling.
    
    Args:
        api_func: API function to call
        *args: Positional arguments for the function
        **kwargs: Keyword arguments for the function
        
    Returns:
        Result: Result object containing success/failure and data/error
    """
    try:
        result = api_func(*args, **kwargs)
        if result is not None:
            return Result.ok(result)
        else:
            return Result.error("API call returned None")
    except Exception as e:
        log_error(f"API call failed: {e}")
        return Result.error(str(e))
