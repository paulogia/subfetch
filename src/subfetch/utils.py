"""Utility functions for subfetch."""

import re
from datetime import date
from pathlib import Path
from typing import Optional


def sanitize_filename(title: str, max_length: int = 100) -> str:
    """
    Sanitize video title for use in filename.

    Removes/replaces illegal filesystem characters and truncates to reasonable length.
    """
    # Remove or replace problematic characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '', title)
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()

    # Truncate if too long (preserve word boundaries if possible)
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rsplit(' ', 1)[0]

    # Fallback for empty result
    if not sanitized:
        sanitized = "untitled"

    return sanitized


def parse_upload_date(date_str: Optional[str]) -> Optional[date]:
    """Parse yt-dlp date format (YYYYMMDD) to date object."""
    if date_str and len(date_str) == 8:
        try:
            return date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
        except ValueError:
            pass
    return None


def find_subtitle_by_video_id(folder: Path, video_id: str) -> Optional[Path]:
    """
    Find subtitle file in folder matching [VIDEO_ID] pattern.

    Returns the first matching file, or None if not found.
    """
    # Can't use glob with [...] as it's interpreted as character class
    # Check both .txt (current format) and .srt (legacy format)
    for f in folder.iterdir():
        if f.suffix in ('.txt', '.srt') and f'[{video_id}]' in f.name:
            return f
    return None


def ensure_unique_folder_name(parent: Path, base_name: str) -> str:
    """
    Generate unique folder name by appending numbers if needed.

    If base_name exists, returns base_name_2, base_name_3, etc.
    """
    candidate = base_name
    counter = 2
    while (parent / candidate).exists():
        candidate = f"{base_name}_{counter}"
        counter += 1
    return candidate
