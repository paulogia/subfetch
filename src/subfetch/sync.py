"""Channel synchronization engine for subfetch."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .channel import ChannelEnumerator
from .config import ArchiveConfig, ChannelConfig
from .extractor import SubtitleExtractor
from .metadata import MetadataManager
from .models import VideoInfo
from .utils import find_subtitle_by_video_id


@dataclass
class SyncProgress:
    """Real-time progress tracking during sync."""
    channel_id: str
    channel_title: str
    total_videos: int
    processed: int
    downloaded: int
    skipped: int
    missing_captions: int
    errors: int


@dataclass
class SyncResult:
    """Summary of sync operation."""
    channels_processed: int
    total_videos: int
    downloaded: int
    skipped: int
    missing_captions: int
    errors: int


class ChannelSynchronizer:
    """Synchronize subtitles for tracked channels."""

    def __init__(self, config: ArchiveConfig, cookies_file: Optional[Path] = None):
        self.config = config
        self.enumerator = ChannelEnumerator()
        self.extractor = SubtitleExtractor(cookies_file=cookies_file)

    def sync_all_channels(
        self,
        max_videos: Optional[int] = None,
        progress_callback: Optional[Callable[[str, VideoInfo, str], None]] = None
    ) -> SyncResult:
        """
        Sync all tracked channels.

        Args:
            max_videos: Optional limit per channel
            progress_callback: Called with (channel_title, video, status) for each video

        Returns:
            SyncResult with aggregate statistics
        """
        result = SyncResult(
            channels_processed=0,
            total_videos=0,
            downloaded=0,
            skipped=0,
            missing_captions=0,
            errors=0
        )

        for channel_config in self.config.channels.values():
            progress = self.sync_channel(
                channel_config.channel_id,
                max_videos=max_videos,
                progress_callback=progress_callback
            )

            result.channels_processed += 1
            result.total_videos += progress.processed
            result.downloaded += progress.downloaded
            result.skipped += progress.skipped
            result.missing_captions += progress.missing_captions
            result.errors += progress.errors

        return result

    def sync_channel(
        self,
        channel_id: str,
        max_videos: Optional[int] = None,
        progress_callback: Optional[Callable[[str, VideoInfo, str], None]] = None
    ) -> SyncProgress:
        """
        Sync single channel by ID.

        Args:
            channel_id: Channel ID to sync
            max_videos: Optional limit on videos to process
            progress_callback: Called with (channel_title, video, status) for each video
                              status is 'downloaded', 'skipped', 'missing_captions', or 'error'

        Returns:
            SyncProgress with channel statistics
        """
        channel_config = self.config.channels.get(channel_id)
        if not channel_config:
            raise ValueError(f"Channel not tracked: {channel_id}")

        # Setup paths
        root = Path(self.config.root_path)
        channel_folder = root / channel_config.folder_name
        channel_folder.mkdir(parents=True, exist_ok=True)

        # Ensure metadata exists
        metadata = MetadataManager.load(channel_folder)
        if metadata is None:
            metadata = MetadataManager.create(
                channel_folder,
                channel_config.channel_id,
                channel_config.channel_title,
                channel_config.channel_url
            )

        # Set extractor output directory
        self.extractor.set_output_dir(channel_folder)

        # Initialize progress
        progress = SyncProgress(
            channel_id=channel_id,
            channel_title=channel_config.channel_title,
            total_videos=0,  # Will be updated as we enumerate
            processed=0,
            downloaded=0,
            skipped=0,
            missing_captions=0,
            errors=0
        )

        videos_added = 0

        # Enumerate and process videos
        for video in self.enumerator.enumerate(channel_id, max_videos=max_videos):
            progress.processed += 1

            # Check if already downloaded
            if self._should_skip_video(channel_folder, video.video_id):
                progress.skipped += 1
                if progress_callback:
                    progress_callback(channel_config.channel_title, video, 'skipped')
                continue

            # Attempt download
            try:
                result = self.extractor.extract(video.url)

                if result.success:
                    progress.downloaded += 1
                    videos_added += 1
                    if progress_callback:
                        progress_callback(channel_config.channel_title, video, 'downloaded')

                    # Append to cumulative file immediately after successful download
                    try:
                        from .cumulative import CumulativeManager
                        CumulativeManager.append_transcripts(
                            channel_folder,
                            channel_config.channel_title,
                            [Path(result.file_path)]
                        )
                    except Exception:
                        # Don't fail download if cumulative append fails
                        pass
                else:
                    # No captions available
                    progress.missing_captions += 1
                    if progress_callback:
                        progress_callback(channel_config.channel_title, video, 'missing_captions')

            except Exception as e:
                progress.errors += 1
                if progress_callback:
                    progress_callback(channel_config.channel_title, video, 'error')

            # Conservative delay between downloads to avoid rate limiting
            time.sleep(2.5)

        # Update metadata
        if videos_added > 0:
            MetadataManager.update(channel_folder, videos_added=videos_added)

        progress.total_videos = progress.processed
        return progress

    def _should_skip_video(self, channel_folder: Path, video_id: str) -> bool:
        """
        Check if video already has subtitle file.

        Uses glob pattern matching to find any file containing [VIDEO_ID].srt
        """
        subtitle_file = find_subtitle_by_video_id(channel_folder, video_id)

        if subtitle_file is None:
            return False

        # Basic corruption check: ensure file is not empty
        try:
            if subtitle_file.stat().st_size > 100:  # Minimum viable subtitle file
                return True
        except OSError:
            pass

        return False
