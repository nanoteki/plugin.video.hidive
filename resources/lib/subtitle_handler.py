# -*- coding: utf-8 -*-
"""
Subtitle handling module for HiDive addon.
Handles SRT to ASS conversion and local caching for proper positioning.
"""

import os
import re
import hashlib
import requests
from typing import List, Dict, Any, Optional, Tuple
import xbmc
import xbmcaddon
import xbmcvfs
from utils import log_info, log_error, log_debug


def get_cache_directory() -> str:
    """
    Get the addon's cache directory for storing subtitle files in Kodi userdata.
    Uses xbmcvfs for proper Kodi file system handling.

    Returns:
        str: Path to cache directory using special:// protocol
    """
    addon = xbmcaddon.Addon()

    # Use the addon's profile directory with special:// protocol
    profile_path = addon.getAddonInfo('profile')

    # Create subdirectory for subtitle cache using special:// protocol
    cache_dir_special = profile_path + 'subtitle_cache/'

    # Translate to filesystem path for directory operations
    cache_dir_fs = xbmcvfs.translatePath(cache_dir_special)

    # Ensure the directory exists using xbmcvfs
    if not xbmcvfs.exists(cache_dir_special):
        try:
            xbmcvfs.mkdirs(cache_dir_special)
            log_info(f"Created subtitle cache directory: {cache_dir_special}")
        except Exception as e:
            log_error(f"Failed to create cache directory {cache_dir_special}: {e}")
            # Fallback to profile root if subdirectory creation fails
            cache_dir_special = profile_path
            log_info(f"Using fallback cache directory: {cache_dir_special}")

    # Log cache directory info for debugging
    log_debug(f"Using cache directory (special://): {cache_dir_special}", True)
    log_debug(f"Using cache directory (filesystem): {cache_dir_fs}", True)
    log_debug(f"Cache directory exists: {xbmcvfs.exists(cache_dir_special)}", True)

    return cache_dir_special


def generate_cache_filename(subtitle_url: str, language: str, video_id: str) -> str:
    """
    Generate a cache filename for a subtitle file following Kodi naming conventions.
    Uses Crunchyroll's approach: language.lang_code.format
    Since we now use video-specific folders, the filename can be simpler.

    Args:
        subtitle_url: URL of the subtitle file
        language: Language code (e.g., 'en-US')
        video_id: Video ID (not used in filename since folder is video-specific)

    Returns:
        str: Cache filename (e.g., 'en-US.en.ass')
    """
    # Extract language code for Kodi (e.g., 'en-US' -> 'en')
    iso_parts = language.split('-')
    lang_code = iso_parts[0] if iso_parts else 'unknown'

    # Use Crunchyroll's filename format: language.lang_code.format
    # This ensures Kodi displays proper language labels
    filename = f"{language}.{lang_code}.ass"

    # Make filename legal for the filesystem
    try:
        import xbmcvfs
        filename = xbmcvfs.makeLegalFilename(filename)

        # Remove trailing slash if present (xbmcvfs quirk)
        if filename.endswith('/'):
            filename = filename[:-1]
    except:
        # Fallback if xbmcvfs not available
        filename = re.sub(r'[^\w\-_.]', '_', filename)

    return filename


def parse_srt_timestamp(timestamp: str) -> float:
    """
    Parse SRT timestamp to seconds.
    
    Args:
        timestamp: SRT timestamp (e.g., '00:07:31,208')
        
    Returns:
        float: Time in seconds
    """
    time_part, ms_part = timestamp.split(',')
    hours, minutes, seconds = map(int, time_part.split(':'))
    milliseconds = int(ms_part)
    
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0


def format_ass_timestamp(seconds: float) -> str:
    """
    Format seconds to ASS timestamp format.
    
    Args:
        seconds: Time in seconds
        
    Returns:
        str: ASS timestamp (e.g., '0:07:31.21')
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    
    return f"{hours}:{minutes:02d}:{secs:05.2f}"


def validate_ass_content(ass_content: str, debug_enabled: bool = False) -> bool:
    """
    Validate ASS content for basic syntax correctness.

    Args:
        ass_content: ASS subtitle content to validate
        debug_enabled: Whether debug logging is enabled

    Returns:
        bool: True if content appears valid
    """
    required_sections = ['[Script Info]', '[V4+ Styles]', '[Events]']

    for section in required_sections:
        if section not in ass_content:
            log_debug(f"ASS validation failed: missing {section}", debug_enabled)
            return False

    # Check for dialogue lines
    dialogue_count = ass_content.count('Dialogue:')
    log_debug(f"ASS validation: found {dialogue_count} dialogue lines", debug_enabled)

    if dialogue_count == 0:
        log_debug("ASS validation failed: no dialogue lines found", debug_enabled)
        return False

    log_debug("ASS validation passed", debug_enabled)
    return True


def convert_srt_to_ass(srt_content: str, base_margin: int = 30, vertical_spacing: int = 20,
                      debug_enabled: bool = False, font_name: str = 'Arial', font_size: int = 18,
                      primary_color: str = '&H00FFFFFF', outline_color: str = '&H00000000',
                      back_color: str = '&H80000000', bold: bool = False, italic: bool = False,
                      outline_width: int = 2, shadow_depth: int = 0) -> str:
    """
    Convert SRT subtitle content to ASS format with proper positioning and custom styling.

    Args:
        srt_content: SRT subtitle content
        base_margin: Base margin from bottom of screen in pixels
        vertical_spacing: Vertical spacing between stacked subtitles in pixels
        debug_enabled: Whether debug logging is enabled
        font_name: Font family name (e.g., 'Arial', 'Times New Roman')
        font_size: Font size in points
        primary_color: Primary text color in ASS format (e.g., '&H00FFFFFF' for white)
        outline_color: Outline/border color in ASS format
        back_color: Background color in ASS format (with alpha channel)
        bold: Whether text should be bold
        italic: Whether text should be italic
        outline_width: Width of text outline/border
        shadow_depth: Depth of text shadow

    Returns:
        str: ASS subtitle content with positioning and custom styling
    """
    # Subtitle positioning constants (in pixels)
    BASE_MARGIN_FROM_BOTTOM = base_margin  # Base margin from bottom of screen (configurable)
    SUBTITLE_VERTICAL_SPACING = vertical_spacing  # Vertical spacing between stacked subtitles (configurable)
    MINIMUM_MARGIN = 10  # Minimum margin to keep subtitles visible

    log_debug("Starting SRT to ASS conversion with custom styling", debug_enabled)
    log_debug(f"Style settings: font={font_name}, size={font_size}, color={primary_color}, bold={bold}, italic={italic}", debug_enabled)

    # Convert boolean values to ASS format (0 or -1)
    bold_val = -1 if bold else 0
    italic_val = -1 if italic else 0

    # Build dynamic ASS style line
    # Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
    style_line = f"Style: Default,{font_name},{font_size},{primary_color},&H000000FF,{outline_color},{back_color},{bold_val},{italic_val},0,0,100,100,0,0,1,{outline_width},{shadow_depth},2,10,10,10,1"

    # ASS header with dynamic style definitions
    ass_header = f"""[Script Info]
Title: HiDive Subtitles
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{style_line}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    # Parse SRT content
    srt_blocks = re.split(r'\n\s*\n', srt_content.strip())
    dialogue_lines = []
    
    # Track overlapping subtitles for positioning
    active_subtitles = []
    
    for block in srt_blocks:
        if not block.strip():
            continue
            
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue
            
        try:
            # Parse subtitle number
            subtitle_num = int(lines[0])
            
            # Parse timing
            timing_line = lines[1]
            start_time, end_time = timing_line.split(' --> ')
            start_seconds = parse_srt_timestamp(start_time.strip())
            end_seconds = parse_srt_timestamp(end_time.strip())
            
            # Join text lines
            text = '\\N'.join(lines[2:])  # \\N is line break in ASS
            
            # Determine vertical position based on overlapping subtitles
            # Remove expired subtitles from active list
            active_subtitles = [(s, e, p) for s, e, p in active_subtitles if e > start_seconds]

            # Calculate position (0 = first subtitle, 1 = second subtitle, etc.)
            position = len(active_subtitles)

            # Add current subtitle to active list
            active_subtitles.append((start_seconds, end_seconds, position))

            # Create ASS dialogue line with positioning
            # MarginV controls vertical position (higher value = more margin from bottom = higher on screen)
            # We want: first subtitle (position 0) = higher on screen (more margin)
            #          second subtitle (position 1) = lower on screen (less margin)
            margin_v = BASE_MARGIN_FROM_BOTTOM - (position * SUBTITLE_VERTICAL_SPACING)

            # Ensure margin doesn't go below minimum to keep subtitles visible
            if margin_v < MINIMUM_MARGIN:
                margin_v = MINIMUM_MARGIN
            
            ass_start = format_ass_timestamp(start_seconds)
            ass_end = format_ass_timestamp(end_seconds)
            
            dialogue_line = f"Dialogue: 0,{ass_start},{ass_end},Default,,0,0,{margin_v},,{text}"
            dialogue_lines.append(dialogue_line)

            # Enhanced debug logging to show positioning logic
            position_desc = "higher" if position == 0 else f"lower (stack {position})"
            log_debug(f"Converted subtitle {subtitle_num}: position={position} ({position_desc}), margin_v={margin_v} (base={BASE_MARGIN_FROM_BOTTOM}, spacing={SUBTITLE_VERTICAL_SPACING}), text='{text[:50]}...'", debug_enabled)
            
        except (ValueError, IndexError) as e:
            log_debug(f"Failed to parse SRT block: {block[:50]}... Error: {e}", debug_enabled)
            continue
    
    # Combine header and dialogue lines
    ass_content = ass_header + '\n'.join(dialogue_lines)

    log_debug(f"SRT to ASS conversion complete. Generated {len(dialogue_lines)} dialogue lines", debug_enabled)

    # Validate the generated ASS content
    if not validate_ass_content(ass_content, debug_enabled):
        log_error("Generated ASS content failed validation")

    return ass_content


def download_and_cache_subtitle(subtitle_url: str, language: str, video_id: str,
                               base_margin: int = 30, vertical_spacing: int = 20,
                               debug_enabled: bool = False, font_name: str = 'Arial',
                               font_size: int = 18, primary_color: str = '&H00FFFFFF',
                               outline_color: str = '&H00000000', back_color: str = '&H80000000',
                               bold: bool = False, italic: bool = False,
                               outline_width: int = 2, shadow_depth: int = 0) -> Optional[str]:
    """
    Download SRT subtitle, convert to ASS, and cache locally using Kodi VFS.
    Creates a unique subfolder for each video like Crunchyroll does.

    Args:
        subtitle_url: URL of the SRT subtitle file
        language: Language code (e.g., 'en-US')
        video_id: Video ID for cache uniqueness
        base_margin: Base margin from bottom of screen in pixels
        vertical_spacing: Vertical spacing between stacked subtitles in pixels
        debug_enabled: Whether debug logging is enabled

    Returns:
        Optional[str]: special:// URL to cached ASS file, or None if failed
    """
    try:
        # Generate cache directory with video-specific subfolder (like Crunchyroll)
        base_cache_dir = get_cache_directory()
        video_cache_dir_special = base_cache_dir + video_id + '/'
        video_cache_dir_fs = xbmcvfs.translatePath(video_cache_dir_special)

        # Ensure the video-specific directory exists
        if not xbmcvfs.exists(video_cache_dir_special):
            xbmcvfs.mkdirs(video_cache_dir_special)
            log_debug(f"Created video cache directory: {video_cache_dir_special}", debug_enabled)

        # Generate cache filename (video_id not needed since it's in the folder path)
        cache_filename = generate_cache_filename(subtitle_url, language, video_id)
        cache_path_special = video_cache_dir_special + cache_filename
        cache_path_fs = xbmcvfs.translatePath(cache_path_special)

        log_debug(f"Caching subtitle: {subtitle_url}", debug_enabled)
        log_debug(f"Base cache directory: {base_cache_dir}", debug_enabled)
        log_debug(f"Video cache directory: {video_cache_dir_special}", debug_enabled)
        log_debug(f"Cache filename: {cache_filename}", debug_enabled)
        log_debug(f"Cache path (special://): {cache_path_special}", debug_enabled)
        log_debug(f"Cache path (filesystem): {cache_path_fs}", debug_enabled)

        # Check if already cached using xbmcvfs
        if xbmcvfs.exists(cache_path_special):
            log_debug(f"Using cached subtitle: {cache_path_special}", debug_enabled)
            return cache_path_special
        
        # Download SRT content
        log_debug(f"Downloading subtitle from: {subtitle_url}", debug_enabled)
        response = requests.get(subtitle_url, timeout=30)
        response.raise_for_status()
        
        srt_content = response.text
        log_debug(f"Downloaded {len(srt_content)} characters of SRT content", debug_enabled)
        
        # Convert SRT to ASS with configurable positioning and styling
        ass_content = convert_srt_to_ass(
            srt_content, base_margin, vertical_spacing, debug_enabled,
            font_name, font_size, primary_color, outline_color, back_color,
            bold, italic, outline_width, shadow_depth
        )

        # Save to cache using xbmcvfs (write to filesystem path)
        try:
            with open(cache_path_fs, 'w', encoding='utf-8') as f:
                f.write(ass_content)
            log_debug(f"ASS file written to filesystem: {cache_path_fs}", debug_enabled)
        except Exception as write_e:
            log_error(f"Failed to write ASS file to {cache_path_fs}: {write_e}")
            return None

        # Verify file was created using xbmcvfs
        if xbmcvfs.exists(cache_path_special):
            # Get file size using filesystem path
            try:
                file_size = os.path.getsize(cache_path_fs)
                log_info(f"Cached subtitle file: {cache_filename} ({file_size} bytes)")
                log_debug(f"ASS file saved with {len(ass_content)} characters", debug_enabled)
                log_debug(f"File accessible via special:// URL: {cache_path_special}", debug_enabled)

                # Verify file is readable
                try:
                    with open(cache_path_fs, 'r', encoding='utf-8') as verify_f:
                        verify_content = verify_f.read(100)  # Read first 100 chars
                        log_debug(f"File verification - first 100 chars: {verify_content}", debug_enabled)
                except Exception as verify_e:
                    log_error(f"Failed to verify cached file {cache_path_fs}: {verify_e}")
                    return None

            except Exception as size_e:
                log_error(f"Failed to get file size for {cache_path_fs}: {size_e}")
        else:
            log_error(f"Failed to create cache file: {cache_path_special}")
            return None

        # Also create a .ssa version in case Kodi prefers that extension
        ssa_path_special = cache_path_special.replace('.ass', '.ssa')
        ssa_path_fs = cache_path_fs.replace('.ass', '.ssa')
        try:
            with open(ssa_path_fs, 'w', encoding='utf-8') as ssa_f:
                ssa_f.write(ass_content)
            log_debug(f"Also created .ssa version: {ssa_path_special}", debug_enabled)
        except Exception as ssa_e:
            log_debug(f"Failed to create .ssa version: {ssa_e}", debug_enabled)

        # Return the special:// URL for Kodi
        return cache_path_special
        
    except Exception as e:
        log_error(f"Failed to download and cache subtitle {subtitle_url}: {e}")
        return None


def process_subtitle_list(subtitles_data: List[Dict[str, Any]], preferred_lang: str,
                         video_id: str, base_margin: int = 30, vertical_spacing: int = 20,
                         debug_enabled: bool = False, font_name: str = 'Arial',
                         font_size: int = 18, primary_color: str = '&H00FFFFFF',
                         outline_color: str = '&H00000000', back_color: str = '&H80000000',
                         bold: bool = False, italic: bool = False,
                         outline_width: int = 2, shadow_depth: int = 0) -> List[str]:
    """
    Process subtitle list by downloading, converting, and caching subtitle files.

    Args:
        subtitles_data: List of subtitle data from API
        preferred_lang: Preferred subtitle language code
        video_id: Video ID for cache uniqueness
        base_margin: Base margin from bottom of screen in pixels
        vertical_spacing: Vertical spacing between stacked subtitles in pixels
        debug_enabled: Whether debug logging is enabled

    Returns:
        List[str]: List of local ASS file paths
    """
    if not subtitles_data:
        log_debug("No subtitle data provided", debug_enabled)
        return []
    
    log_debug(f"Processing {len(subtitles_data)} subtitle entries for caching", debug_enabled)
    
    # Filter for SRT format subtitles
    srt_subs = [s for s in subtitles_data if s.get('format') == 'srt']
    log_debug(f"Found {len(srt_subs)} SRT format subtitles", debug_enabled)
    
    # Separate preferred and other subtitles
    preferred_subs = [s for s in srt_subs if s.get('language') == preferred_lang]
    other_subs = [s for s in srt_subs if s.get('language') != preferred_lang]
    
    log_debug(f"Preferred language '{preferred_lang}' subtitles: {len(preferred_subs)}", debug_enabled)
    log_debug(f"Other language subtitles: {len(other_subs)}", debug_enabled)
    
    # Process subtitles in order (preferred first)
    cached_files = []
    all_subs = preferred_subs + other_subs
    
    for sub in all_subs:
        subtitle_url = sub.get('url')
        language = sub.get('language', 'unknown')
        
        if not subtitle_url:
            continue
            
        log_debug(f"Processing subtitle: {language} - {subtitle_url}", debug_enabled)
        
        cached_path = download_and_cache_subtitle(
            subtitle_url, language, video_id, base_margin, vertical_spacing, debug_enabled,
            font_name, font_size, primary_color, outline_color, back_color,
            bold, italic, outline_width, shadow_depth
        )
        if cached_path:
            cached_files.append(cached_path)
            log_debug(f"Successfully cached: {cached_path}", debug_enabled)
        else:
            log_debug(f"Failed to cache subtitle: {subtitle_url}", debug_enabled)
    
    log_debug(f"Final cached subtitle files: {cached_files}", debug_enabled)
    return cached_files


def cleanup_old_cache_files(max_age_days: int = 7) -> None:
    """
    Clean up old cached subtitle files using xbmcvfs.
    Now handles video-specific subfolders like Crunchyroll.

    Args:
        max_age_days: Maximum age of cache files in days
    """
    try:
        import time
        cache_dir_special = get_cache_directory()
        cache_dir_fs = xbmcvfs.translatePath(cache_dir_special)
        current_time = time.time()
        max_age_seconds = max_age_days * 24 * 60 * 60

        if not xbmcvfs.exists(cache_dir_special):
            return

        cleaned_count = 0
        cleaned_dirs = 0

        try:
            # List video directories (subfolders)
            video_dirs, files = xbmcvfs.listdir(cache_dir_special)

            # Clean up any loose files in the root cache directory (shouldn't exist with new structure)
            for filename in files:
                if filename.endswith(('.ass', '.ssa')):
                    file_path_special = cache_dir_special + filename
                    if xbmcvfs.delete(file_path_special):
                        log_debug(f"Cleaned up loose cache file: {filename}", True)
                        cleaned_count += 1

            # Clean up video-specific directories
            for video_dir in video_dirs:
                video_dir_special = cache_dir_special + video_dir + '/'
                video_dir_fs = os.path.join(cache_dir_fs, video_dir)

                try:
                    # Check if the entire directory is old
                    dir_age = current_time - os.path.getmtime(video_dir_fs)
                    if dir_age > max_age_seconds:
                        # Remove entire directory
                        if xbmcvfs.rmdir(video_dir_special, force=True):
                            log_debug(f"Cleaned up old video cache directory: {video_dir}", True)
                            cleaned_dirs += 1
                        else:
                            log_debug(f"Failed to delete old video cache directory: {video_dir}", True)
                    else:
                        # Directory is recent, but check individual files
                        try:
                            sub_dirs, sub_files = xbmcvfs.listdir(video_dir_special)
                            for sub_filename in sub_files:
                                if sub_filename.endswith(('.ass', '.ssa')):
                                    sub_file_path_fs = os.path.join(video_dir_fs, sub_filename)
                                    sub_file_path_special = video_dir_special + sub_filename

                                    try:
                                        file_age = current_time - os.path.getmtime(sub_file_path_fs)
                                        if file_age > max_age_seconds:
                                            if xbmcvfs.delete(sub_file_path_special):
                                                log_debug(f"Cleaned up old cache file: {video_dir}/{sub_filename}", True)
                                                cleaned_count += 1
                                    except Exception as file_e:
                                        log_debug(f"Error checking file age for {video_dir}/{sub_filename}: {file_e}", True)
                        except Exception as sub_list_e:
                            log_debug(f"Failed to list video directory {video_dir}: {sub_list_e}", True)

                except Exception as dir_e:
                    log_debug(f"Error checking directory age for {video_dir}: {dir_e}", True)

        except Exception as list_e:
            log_debug(f"Failed to list cache directory for cleanup: {list_e}", True)

        if cleaned_count > 0 or cleaned_dirs > 0:
            log_info(f"Cleaned up {cleaned_count} old subtitle files and {cleaned_dirs} old directories")

    except Exception as e:
        log_error(f"Failed to cleanup cache files: {e}")


def get_cache_info() -> Dict[str, Any]:
    """
    Get information about the subtitle cache for debugging.
    Now handles video-specific subfolders.

    Returns:
        Dict containing cache directory info and file count
    """
    try:
        cache_dir_special = get_cache_directory()
        cache_dir_fs = xbmcvfs.translatePath(cache_dir_special)

        cache_info = {
            'directory': cache_dir_special,
            'directory_fs': cache_dir_fs,
            'exists': xbmcvfs.exists(cache_dir_special),
            'writable': True,  # Assume writable if we can create the directory
            'video_dirs': 0,
            'total_files': 0,
            'video_directories': []
        }

        if xbmcvfs.exists(cache_dir_special):
            try:
                # Use xbmcvfs to list directory contents
                video_dirs, loose_files = xbmcvfs.listdir(cache_dir_special)

                cache_info['video_dirs'] = len(video_dirs)

                # Count loose files (shouldn't exist with new structure)
                loose_subtitle_files = [f for f in loose_files if f.endswith(('.ass', '.ssa'))]
                cache_info['total_files'] = len(loose_subtitle_files)

                # Examine video directories
                for video_dir in video_dirs[:5]:  # Show first 5 video directories
                    video_dir_special = cache_dir_special + video_dir + '/'
                    try:
                        sub_dirs, sub_files = xbmcvfs.listdir(video_dir_special)
                        subtitle_files = [f for f in sub_files if f.endswith(('.ass', '.ssa'))]
                        cache_info['video_directories'].append({
                            'video_id': video_dir,
                            'file_count': len(subtitle_files),
                            'files': subtitle_files
                        })
                        cache_info['total_files'] += len(subtitle_files)
                    except Exception as sub_e:
                        cache_info['video_directories'].append({
                            'video_id': video_dir,
                            'error': str(sub_e)
                        })

            except Exception as list_e:
                log_debug(f"Failed to list cache directory contents: {list_e}", True)
                cache_info['list_error'] = str(list_e)

        return cache_info
    except Exception as e:
        log_error(f"Failed to get cache info: {e}")
        return {'error': str(e)}
