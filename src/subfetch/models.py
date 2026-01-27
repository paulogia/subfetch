"""Data models for subfetch."""

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Optional


class SubtitleType(Enum):
    """Type of subtitle source."""
    UPLOADED = "uploaded"
    AUTO_GENERATED = "auto-generated"
    TRANSLATED = "translated"


@dataclass
class VideoInfo:
    """Video metadata."""
    video_id: str
    title: str
    url: str
    upload_date: Optional[date] = None
    channel_id: Optional[str] = None
    channel_title: Optional[str] = None


@dataclass
class SubtitleResult:
    """Result of a subtitle extraction attempt."""
    video: VideoInfo
    success: bool
    subtitle_type: Optional[SubtitleType] = None
    file_path: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ChannelInfo:
    """Extended channel information."""
    channel_id: str
    channel_title: str
    channel_url: str
    total_videos: int
