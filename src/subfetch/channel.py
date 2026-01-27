"""Channel video enumeration using yt-dlp."""

from typing import Iterator, Optional

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

    def enumerate(self, channel_identifier: str, max_videos: Optional[int] = None) -> Iterator[VideoInfo]:
        """
        Enumerate all public videos from a channel.

        Args:
            channel_identifier: Channel URL, @handle, or channel ID
            max_videos: Optional limit on number of videos to return

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
                channel_id = info.get('channel_id')
                channel_title = info.get('channel')

                count = 0
                for entry in entries:
                    if entry is None:
                        continue

                    if max_videos and count >= max_videos:
                        break

                    video_id = entry.get('id', '')
                    yield VideoInfo(
                        video_id=video_id,
                        title=entry.get('title', ''),
                        url=f"https://www.youtube.com/watch?v={video_id}",
                        channel_id=channel_id,
                        channel_title=channel_title,
                        upload_date=parse_upload_date(entry.get('upload_date')),
                    )
                    count += 1
        except Exception:
            return

    def get_channel_info(self, identifier: str) -> Optional[dict]:
        """Get channel metadata (id, title, etc.)."""
        channel_url = self._normalize_channel_url(identifier)

        try:
            with yt_dlp.YoutubeDL(self._ydl_opts) as ydl:
                info = ydl.extract_info(channel_url, download=False)
                if info:
                    return {
                        'channel_id': info.get('channel_id'),
                        'channel_title': info.get('channel'),
                        'channel_url': info.get('channel_url'),
                        'video_count': len(info.get('entries', [])),
                    }
        except Exception:
            pass
        return None

    def _normalize_channel_url(self, identifier: str) -> str:
        """
        Convert various channel identifier formats to videos URL.

        Handles:
        - @handle -> https://www.youtube.com/@handle/videos
        - channel ID -> https://www.youtube.com/channel/{id}/videos
        - Full URL -> append /videos if needed
        """
        identifier = identifier.strip()

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
