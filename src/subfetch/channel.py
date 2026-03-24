"""Channel video enumeration using yt-dlp."""

import re
from typing import Callable, Iterator, Optional

import yt_dlp

from .models import VideoInfo
from .utils import parse_upload_date


class ChannelEnumerator:
    """Enumerate all videos from a YouTube channel."""

    def __init__(self):
        self._ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': 'in_playlist',
            'skip_download': True,
        }

    @staticmethod
    def is_playlist_url(identifier: str) -> bool:
        """Detect if identifier is a playlist URL."""
        identifier = identifier.strip()
        identifier_lower = identifier.lower()

        # Check for playlist URL patterns
        if ('/playlist' in identifier_lower or
            '?list=' in identifier_lower or
            '&list=' in identifier_lower):
            return True

        # Check for bare playlist ID (starts with known playlist prefixes)
        if identifier.startswith(('PL', 'RD', 'UU', 'FL', 'LP', 'LL')):
            return True

        return False

    @staticmethod
    def extract_playlist_id(url: str) -> Optional[str]:
        """Extract playlist ID from URL (e.g., 'PLxxx')."""
        match = re.search(r'[?&]list=([^&]+)', url)
        return match.group(1) if match else None

    @staticmethod
    def normalize_playlist_url(identifier: str) -> str:
        """Convert playlist identifier to canonical URL."""
        identifier = identifier.strip()

        # Bare playlist ID (starts with PL, RD, UU, FL, LP, LL)
        if identifier.startswith(('PL', 'RD', 'UU', 'FL', 'LP', 'LL')):
            return f"https://www.youtube.com/playlist?list={identifier}"

        # Extract from URL
        playlist_id = ChannelEnumerator.extract_playlist_id(identifier)
        if playlist_id:
            return f"https://www.youtube.com/playlist?list={playlist_id}"

        return identifier

    def enumerate(
        self,
        channel_identifier: str,
        max_videos: Optional[int] = None,
        on_total: Optional[Callable[[int], None]] = None,
    ) -> Iterator[VideoInfo]:
        """
        Enumerate all public videos from a channel.

        Args:
            channel_identifier: Channel URL, @handle, or channel ID
            max_videos: Optional limit on number of videos to return
            on_total: Optional callback called with the total video count before
                      the first video is yielded (no extra API call required)

        Yields:
            VideoInfo for each video found
        """
        channel_url = self._normalize_channel_url(channel_identifier)

        try:
            with yt_dlp.YoutubeDL(self._ydl_opts) as ydl:
                info = ydl.extract_info(channel_url, download=False)

                if info is None:
                    return

                entries = info.get('entries', [])
                if on_total is not None:
                    on_total(len(entries))
                channel_id = info.get('channel_id')
                channel_title = info.get('channel')

                count = 0
                for entry in entries:
                    if entry is None:
                        continue

                    if max_videos and count >= max_videos:
                        break

                    # Skip currently-live and upcoming streams — they have no subtitles
                    live_status = entry.get('live_status')
                    if live_status in ('is_live', 'is_upcoming'):
                        continue

                    video_id = entry.get('id', '')
                    yield VideoInfo(
                        video_id=video_id,
                        title=entry.get('title', ''),
                        url=f"https://www.youtube.com/watch?v={video_id}",
                        channel_id=channel_id,
                        channel_title=channel_title,
                        upload_date=parse_upload_date(entry.get('upload_date')),
                        is_live=live_status == 'was_live',
                    )
                    count += 1
        except Exception:
            return

    def enumerate_live(
        self,
        channel_identifier: str,
        on_total: Optional[Callable[[int], None]] = None,
    ) -> Iterator[VideoInfo]:
        """
        Enumerate live stream replays from a channel's /streams tab.

        Yields VideoInfo with is_live=True for every entry.
        Returns empty iterator for playlists or channels with no streams tab.
        """
        live_url = self._to_streams_url(channel_identifier)
        if not live_url:
            return

        try:
            with yt_dlp.YoutubeDL(self._ydl_opts) as ydl:
                info = ydl.extract_info(live_url, download=False)

                if info is None:
                    return

                entries = info.get('entries', [])
                if on_total is not None:
                    on_total(len(entries))
                channel_id = info.get('channel_id')
                channel_title = info.get('channel')

                for entry in entries:
                    if entry is None:
                        continue

                    # Skip streams that are still live or upcoming
                    live_status = entry.get('live_status')
                    if live_status in ('is_live', 'is_upcoming'):
                        continue

                    video_id = entry.get('id', '')
                    yield VideoInfo(
                        video_id=video_id,
                        title=entry.get('title', ''),
                        url=f"https://www.youtube.com/watch?v={video_id}",
                        channel_id=channel_id,
                        channel_title=channel_title,
                        upload_date=parse_upload_date(entry.get('upload_date')),
                        is_live=True,  # Everything from /streams is a live replay
                    )
        except Exception:
            return

    def _to_streams_url(self, identifier: str) -> Optional[str]:
        """Convert channel identifier to its /streams tab URL. Returns None for playlists."""
        identifier = identifier.strip()

        if self.is_playlist_url(identifier):
            return None

        if identifier.startswith('@'):
            return f"https://www.youtube.com/{identifier}/streams"
        elif identifier.startswith('UC') and len(identifier) == 24:
            return f"https://www.youtube.com/channel/{identifier}/streams"
        elif 'youtube.com' in identifier:
            url = identifier.rstrip('/')
            # Replace /videos or /streams suffix, then append /streams
            url = re.sub(r'/(videos|streams)$', '', url)
            return url + '/streams'
        else:
            return f"https://www.youtube.com/@{identifier}/streams"

    def get_channel_info(self, identifier: str) -> Optional[dict]:
        """Get channel or playlist metadata."""
        normalized_url = self._normalize_channel_url(identifier)
        is_playlist = self.is_playlist_url(normalized_url)

        try:
            with yt_dlp.YoutubeDL(self._ydl_opts) as ydl:
                info = ydl.extract_info(normalized_url, download=False)
                if info:
                    if is_playlist:
                        return {
                            'channel_id': info.get('id'),           # Playlist ID
                            'channel_title': info.get('title'),     # Playlist title
                            'channel_url': normalized_url,
                            'video_count': len(info.get('entries', [])),
                            'source_type': 'playlist',
                            'owner_channel_id': info.get('channel_id'),    # Creator
                            'owner_channel_name': info.get('channel')      # Creator name
                        }
                    else:
                        # Existing channel logic + add source_type
                        return {
                            'channel_id': info.get('channel_id'),
                            'channel_title': info.get('channel'),
                            'channel_url': info.get('channel_url'),
                            'video_count': len(info.get('entries', [])),
                            'source_type': 'channel'
                        }
        except Exception:
            pass
        return None

    def _normalize_channel_url(self, identifier: str) -> str:
        """
        Convert various channel/playlist identifier formats to canonical URL.

        Handles:
        - Playlist URLs or IDs -> https://www.youtube.com/playlist?list={id}
        - @handle -> https://www.youtube.com/@handle/videos
        - channel ID -> https://www.youtube.com/channel/{id}/videos
        - Full URL -> append /videos if needed
        """
        identifier = identifier.strip()

        # Check if playlist first
        if self.is_playlist_url(identifier):
            return self.normalize_playlist_url(identifier)

        if identifier.startswith('@'):
            return f"https://www.youtube.com/{identifier}/videos"
        elif identifier.startswith('UC') and len(identifier) == 24:
            # Looks like a channel ID
            return f"https://www.youtube.com/channel/{identifier}/videos"
        elif 'youtube.com' in identifier:
            # Already a URL, ensure it ends with /videos
            url = identifier.rstrip('/')
            if not url.endswith('/videos'):
                url = url + '/videos'
            return url
        else:
            # Assume it's a handle without @
            return f"https://www.youtube.com/@{identifier}/videos"
