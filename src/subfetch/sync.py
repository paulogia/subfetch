"""Channel synchronization engine for subfetch."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, Optional

from .channel import ChannelEnumerator
from .config import ArchiveConfig, ChannelConfig
from .extractor import UPCOMING_LIVE_ERROR, SubtitleExtractor
from .metadata import ErrorTracker, LiveVideoTracker, MetadataManager, NoSubtitlesTracker
from .models import VideoInfo
from .utils import find_subtitle_by_video_id


def _is_fresh(upload_date: Optional[date], grace_days: int) -> bool:
    """Return True if a video is within the grace window (too fresh to record a strike)."""
    if upload_date is None:
        return True  # Unknown date — treat as fresh
    return (date.today() - upload_date).days < grace_days


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
    rate_limited: bool = False  # True if stopped due to rate limiting detection
    skipped_no_subtitles: int = 0  # Videos skipped because confirmed no subtitles
    skipped_errored: int = 0  # Videos skipped because error threshold reached
    total_channel_videos: int = 0  # Total videos in channel (0 if unknown)


@dataclass
class SyncResult:
    """Summary of sync operation."""
    channels_processed: int
    total_videos: int
    downloaded: int
    skipped: int
    missing_captions: int
    errors: int
    rate_limited: bool = False  # True if stopped early due to rate limiting
    skipped_no_subtitles: int = 0  # Videos skipped because confirmed no subtitles
    skipped_errored: int = 0  # Videos skipped because error threshold reached


class ChannelSynchronizer:
    """Synchronize subtitles for tracked channels."""

    def __init__(
        self,
        config: ArchiveConfig,
        cookies_file: Optional[Path] = None,
        cookies_from_browser: Optional[str] = None,
    ):
        self.config = config
        self.enumerator = ChannelEnumerator()
        self.extractor = SubtitleExtractor(
            cookies_file=cookies_file,
            cookies_from_browser=cookies_from_browser,
        )

    def sync_all_channels(
        self,
        max_videos: Optional[int] = None,
        progress_callback: Optional[Callable[[str, VideoInfo, str], None]] = None,
        delay: float = 2.5,
        max_consecutive_failures: int = 10
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
                progress_callback=progress_callback,
                delay=delay,
                max_consecutive_failures=max_consecutive_failures
            )

            result.channels_processed += 1
            result.total_videos += progress.processed
            result.downloaded += progress.downloaded
            result.skipped += progress.skipped
            result.missing_captions += progress.missing_captions
            result.errors += progress.errors
            result.skipped_no_subtitles += progress.skipped_no_subtitles
            result.skipped_errored += progress.skipped_errored

            if progress.rate_limited:
                result.rate_limited = True
                break

        return result

    def sync_channel(
        self,
        channel_id: str,
        max_videos: Optional[int] = None,
        progress_callback: Optional[Callable[[str, VideoInfo, str], None]] = None,
        delay: float = 2.5,
        max_consecutive_failures: int = 10,
        no_sub_threshold: int = 2,
        live_grace_days: int = 7,
    ) -> SyncProgress:
        """
        Sync single channel by ID.

        Args:
            channel_id: Channel ID to sync
            max_videos: Optional limit on videos to process
            progress_callback: Called with (channel_title, video, status) for each video
                              status is 'downloaded', 'skipped', 'missing_captions', or 'error'
            delay: Seconds to wait between videos
            max_consecutive_failures: Stop after this many consecutive missing captions or errors (likely rate limiting)
            no_sub_threshold: Skip permanently after this many confirmed no-subtitle results (default 2)
            live_grace_days: Days a live stream video is exempt from no-subtitle strikes (default 7)

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
        consecutive_failures = 0
        new_videos_attempted = 0  # Count of non-skipped videos attempted

        def _on_total(n: int) -> None:
            progress.total_channel_videos = n

        # Enumerate and process videos (no max_videos cap on enumeration;
        # max_videos limits how many *new* videos we attempt, not how many we scan)
        for video in self.enumerator.enumerate(channel_id, on_total=_on_total):
            progress.processed += 1

            # Check if already downloaded
            if self._should_skip_video(channel_folder, video.video_id):
                progress.skipped += 1
                consecutive_failures = 0  # Reset on skip
                if progress_callback:
                    progress_callback(channel_config.channel_title, video, 'skipped')
                continue

            # Skip live streams silently for channels that don't have include_lives set
            if video.is_live and not channel_config.include_lives:
                progress.skipped += 1
                continue

            # Check if confirmed no subtitles (persistent across runs)
            if NoSubtitlesTracker.should_skip(video.video_id, channel_folder, threshold=no_sub_threshold):
                progress.skipped_no_subtitles += 1
                consecutive_failures = 0
                if progress_callback:
                    progress_callback(channel_config.channel_title, video, 'skipped_no_subtitles')
                continue

            # Check if video has hit the error threshold (e.g. members-only, deleted)
            if ErrorTracker.should_skip(video.video_id, channel_folder, threshold=no_sub_threshold):
                progress.skipped_errored += 1
                consecutive_failures = 0
                if progress_callback:
                    progress_callback(channel_config.channel_title, video, 'skipped_errored')
                continue

            # Stop once we've attempted enough new videos
            if max_videos is not None and new_videos_attempted >= max_videos:
                break

            new_videos_attempted += 1

            # Attempt download
            try:
                result = self.extractor.extract(video.url)

                if result.success:
                    progress.downloaded += 1
                    videos_added += 1
                    consecutive_failures = 0  # Reset on success
                    if progress_callback:
                        progress_callback(channel_config.channel_title, video, 'downloaded')

                    # Append to cumulative file immediately after successful download.
                    # Live streams get their own "-live" cumulative series.
                    try:
                        from .cumulative import CumulativeManager
                        cumulative_title = (
                            f"{channel_config.channel_title}-live"
                            if video.is_live
                            else channel_config.channel_title
                        )
                        CumulativeManager.append_transcripts(
                            channel_folder,
                            cumulative_title,
                            [Path(result.file_path)]
                        )
                        if video.is_live:
                            LiveVideoTracker.add(video.video_id, channel_folder)
                    except Exception:
                        # Don't fail download if cumulative append fails
                        pass
                elif result.error == "No English subtitles available":
                    # Permanent: yt-dlp confirmed no English tracks exist.
                    # For fresh live streams, skip recording the strike — subtitles
                    # may not be available yet and will appear within days.
                    progress.missing_captions += 1
                    consecutive_failures += 1
                    fresh_live = (
                        video.is_live
                        and channel_config.include_lives
                        and _is_fresh(video.upload_date, live_grace_days)
                    )
                    if not fresh_live:
                        NoSubtitlesTracker.record_attempt(video.video_id, channel_folder)
                    if progress_callback:
                        progress_callback(channel_config.channel_title, video, 'missing_captions')

                    # Check if we've hit too many consecutive failures (likely rate limiting)
                    if consecutive_failures >= max_consecutive_failures:
                        progress.rate_limited = True
                        break

                elif result.error == UPCOMING_LIVE_ERROR:
                    # Scheduled live/premiere that hasn't aired: no strike, no
                    # failure count — it will resolve itself once the event airs.
                    progress.errors += 1
                    if progress_callback:
                        progress_callback(channel_config.channel_title, video, 'error')

                else:
                    # Transient error — treat same as missing captions for stop heuristic
                    # since we can't reliably distinguish rate limiting from other failures
                    progress.errors += 1
                    consecutive_failures += 1
                    ErrorTracker.record_attempt(video.video_id, channel_folder)
                    if progress_callback:
                        progress_callback(channel_config.channel_title, video, 'error')

                    if consecutive_failures >= max_consecutive_failures:
                        progress.rate_limited = True
                        break

            except Exception:
                progress.errors += 1
                consecutive_failures += 1
                ErrorTracker.record_attempt(video.video_id, channel_folder)
                if progress_callback:
                    progress_callback(channel_config.channel_title, video, 'error')

                if consecutive_failures >= max_consecutive_failures:
                    progress.rate_limited = True
                    break

            # Conservative delay between downloads to avoid rate limiting
            time.sleep(delay)

        # Enumerate the /streams tab for channels with include_lives.
        # The /videos tab either omits live replays or doesn't reliably mark them,
        # so we query the streams tab directly.
        if channel_config.include_lives and not progress.rate_limited:
            def _on_live_total(n: int) -> None:
                progress.total_channel_videos += n

            live_videos_attempted = 0
            for video in self.enumerator.enumerate_live(channel_id, on_total=_on_live_total):
                progress.processed += 1

                if self._should_skip_video(channel_folder, video.video_id):
                    progress.skipped += 1
                    consecutive_failures = 0
                    if progress_callback:
                        progress_callback(channel_config.channel_title, video, 'skipped')
                    continue

                if NoSubtitlesTracker.should_skip(video.video_id, channel_folder, threshold=no_sub_threshold):
                    progress.skipped_no_subtitles += 1
                    consecutive_failures = 0
                    if progress_callback:
                        progress_callback(channel_config.channel_title, video, 'skipped_no_subtitles')
                    continue

                if ErrorTracker.should_skip(video.video_id, channel_folder, threshold=no_sub_threshold):
                    progress.skipped_errored += 1
                    consecutive_failures = 0
                    if progress_callback:
                        progress_callback(channel_config.channel_title, video, 'skipped_errored')
                    continue

                # Respect max_videos cap for live streams (same semantics as main loop)
                if max_videos is not None and live_videos_attempted >= max_videos:
                    break
                live_videos_attempted += 1

                try:
                    result = self.extractor.extract(video.url)

                    if result.success:
                        progress.downloaded += 1
                        videos_added += 1
                        consecutive_failures = 0
                        if progress_callback:
                            progress_callback(channel_config.channel_title, video, 'downloaded')
                        try:
                            from .cumulative import CumulativeManager
                            CumulativeManager.append_transcripts(
                                channel_folder,
                                f"{channel_config.channel_title}-live",
                                [Path(result.file_path)]
                            )
                            LiveVideoTracker.add(video.video_id, channel_folder)
                        except Exception:
                            pass
                    elif result.error == "No English subtitles available":
                        progress.missing_captions += 1
                        consecutive_failures += 1
                        if not _is_fresh(video.upload_date, live_grace_days):
                            NoSubtitlesTracker.record_attempt(video.video_id, channel_folder)
                        if progress_callback:
                            progress_callback(channel_config.channel_title, video, 'missing_captions')
                        if consecutive_failures >= max_consecutive_failures:
                            progress.rate_limited = True
                            break
                    elif result.error == UPCOMING_LIVE_ERROR:
                        progress.errors += 1
                        if progress_callback:
                            progress_callback(channel_config.channel_title, video, 'error')
                    else:
                        progress.errors += 1
                        consecutive_failures += 1
                        ErrorTracker.record_attempt(video.video_id, channel_folder)
                        if progress_callback:
                            progress_callback(channel_config.channel_title, video, 'error')
                        if consecutive_failures >= max_consecutive_failures:
                            progress.rate_limited = True
                            break

                except Exception:
                    progress.errors += 1
                    consecutive_failures += 1
                    ErrorTracker.record_attempt(video.video_id, channel_folder)
                    if progress_callback:
                        progress_callback(channel_config.channel_title, video, 'error')
                    if consecutive_failures >= max_consecutive_failures:
                        progress.rate_limited = True
                        break

                time.sleep(delay)

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
