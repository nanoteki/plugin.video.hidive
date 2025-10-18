# -*- coding: utf-8 -*-
"""
Configuration management module using functional programming principles.
Provides immutable configuration objects and pure functions for settings access.
"""

from typing import NamedTuple, Optional, Dict, Any
import xbmcaddon


def _get_dashboard_buckets_count(addon: xbmcaddon.Addon) -> int:
    """
    Helper function to safely get dashboard buckets count setting.

    Args:
        addon: The Kodi addon instance

    Returns:
        int: Dashboard buckets count with safe fallback
    """
    try:
        value = addon.getSettingInt('dashboard_buckets_count')
        # Ensure value is within valid range (5-15)
        return max(5, min(15, value if value > 0 else 10))
    except (ValueError, TypeError):
        return 10  # HiDive API limit - requesting more returns same result


def _get_dashboard_entries_per_bucket(addon: xbmcaddon.Addon) -> int:
    """
    Helper function to safely get dashboard entries per bucket setting.

    Args:
        addon: The Kodi addon instance

    Returns:
        int: Dashboard entries per bucket with safe fallback
    """
    try:
        value = addon.getSettingInt('dashboard_entries_per_bucket')
        # Ensure value is within valid range (10-50)
        return max(10, min(50, value if value > 0 else 25))
    except (ValueError, TypeError):
        return 25  # Good balance of content vs performance - matches Artemis app default


class AppConfig(NamedTuple):
    """Immutable configuration object containing all app settings."""
    username: str
    password: str
    auth_token: str
    active_profile_id: str
    preferred_audio_language: str
    enable_subtitles: bool
    preferred_subtitle_language: str
    subtitle_fallback: bool
    enable_debug_logging: bool
    subtitle_base_margin: int
    subtitle_vertical_spacing: int
    # Subtitle styling options
    subtitle_font_name: str
    subtitle_font_size: int
    subtitle_primary_color: str
    subtitle_outline_color: str
    subtitle_back_color: str
    subtitle_bold: bool
    subtitle_italic: bool
    subtitle_outline_width: int
    subtitle_shadow_depth: int
    # Dashboard settings - user-configurable through addon settings
    dashboard_buckets_count: int
    dashboard_entries_per_bucket: int
    enable_dashboard_pagination: bool
    enable_enhanced_bucket_loading: bool
    addon_handle: Optional[int] = None
    base_url: Optional[str] = None


class LanguageConfig(NamedTuple):
    """Immutable language configuration mappings."""
    audio_lang_map: Dict[str, str]
    subtitle_lang_map: Dict[str, str]


def create_config(addon: xbmcaddon.Addon, addon_handle: Optional[int] = None,
                  base_url: Optional[str] = None) -> AppConfig:
    """
    function to create an immutable configuration object from addon settings.

    Args:
        addon: The Kodi addon instance
        addon_handle: Optional addon handle for Kodi plugin
        base_url: Optional base URL for the plugin

    Returns:
        AppConfig: Immutable configuration object
    """
    return AppConfig(
        username=addon.getSetting('hidive_username'),
        password=addon.getSetting('hidive_password'),
        auth_token=addon.getSetting('auth_token'),
        active_profile_id=addon.getSetting('active_profile_id'),
        preferred_audio_language=addon.getSetting('preferred_audio_language'),
        enable_subtitles=addon.getSettingBool('enable_subtitles'),
        preferred_subtitle_language=addon.getSetting('preferred_subtitle_language'),
        subtitle_fallback=addon.getSettingBool('subtitle_fallback'),
        enable_debug_logging=addon.getSettingBool('enable_debug_logging'),
        subtitle_base_margin=addon.getSettingInt('subtitle_base_margin'),
        subtitle_vertical_spacing=addon.getSettingInt('subtitle_vertical_spacing'),
        # Subtitle styling settings with defaults
        subtitle_font_name=addon.getSetting('subtitle_font_name') or 'Arial',
        subtitle_font_size=addon.getSettingInt('subtitle_font_size') or 18,
        subtitle_primary_color=addon.getSetting('subtitle_primary_color') or '&H00FFFFFF',
        subtitle_outline_color=addon.getSetting('subtitle_outline_color') or '&H00000000',
        subtitle_back_color=addon.getSetting('subtitle_back_color') or '&H80000000',
        subtitle_bold=addon.getSettingBool('subtitle_bold'),
        subtitle_italic=addon.getSettingBool('subtitle_italic'),
        subtitle_outline_width=addon.getSettingInt('subtitle_outline_width') or 2,
        subtitle_shadow_depth=addon.getSettingInt('subtitle_shadow_depth') or 0,
        # Dashboard settings with safe defaults
        dashboard_buckets_count=_get_dashboard_buckets_count(addon),
        dashboard_entries_per_bucket=_get_dashboard_entries_per_bucket(addon),
        enable_dashboard_pagination=addon.getSettingBool('enable_dashboard_pagination'),
        enable_enhanced_bucket_loading=addon.getSettingBool('enable_enhanced_bucket_loading'),
        addon_handle=addon_handle,
        base_url=base_url
    )


def get_language_config() -> LanguageConfig:
    """
    function to get language configuration mappings.
    
    Returns:
        LanguageConfig: Immutable language configuration
    """
    return LanguageConfig(
        audio_lang_map={"English": "eng", "Japanese": "jpn"},
        subtitle_lang_map={"English": "en-US"}
    )


def update_auth_settings(addon: xbmcaddon.Addon, auth_token: str = '', 
                        profile_id: str = '') -> None:
    """
    Side effect function to update authentication settings.
    Separated from pure functions for clear side effect management.
    
    Args:
        addon: The Kodi addon instance
        auth_token: Authentication token to save
        profile_id: Profile ID to save
    """
    addon.setSetting('auth_token', auth_token)
    addon.setSetting('active_profile_id', profile_id)


def has_credentials(config: AppConfig) -> bool:
    """
    function to check if credentials are available.
    
    Args:
        config: Application configuration
        
    Returns:
        bool: True if both username and password are present
    """
    return bool(config.username and config.password)


def has_auth_token(config: AppConfig) -> bool:
    """
    function to check if auth token is available.
    
    Args:
        config: Application configuration
        
    Returns:
        bool: True if auth token is present
    """
    return bool(config.auth_token)


def has_active_profile(config: AppConfig) -> bool:
    """
    function to check if active profile is set.
    
    Args:
        config: Application configuration
        
    Returns:
        bool: True if active profile ID is present
    """
    return bool(config.active_profile_id)
