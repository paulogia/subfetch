"""Subtitle extraction using yt-dlp."""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Optional

import yt_dlp

from .models import SubtitleResult, SubtitleType, VideoInfo
from .transform import simplify_srt
from .utils import parse_upload_date, sanitize_filename

# Debug mode controlled by environment variable
DEBUG = os.environ.get('SUBFETCH_DEBUG', '').lower() in ('1', 'true', 'yes')

# Scheduled live streams / premieres that haven't aired yet. These must not
# accrue error strikes — they resolve on their own once the event airs.
UPCOMING_LIVE_ERROR = "Upcoming live event"
_UPCOMING_PATTERNS = ('live event will begin', 'premieres in', 'premiere will begin')


def _is_upcoming_error(text: str) -> bool:
    text = text.lower()
    return any(p in text for p in _UPCOMING_PATTERNS)


def _ms_to_srt_time(ms: int) -> str:
    h = ms // 3_600_000
    ms %= 3_600_000
    m = ms // 60_000
    ms %= 60_000
    s = ms // 1_000
    ms %= 1_000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _json3_to_srt(raw: str) -> str:
    """Convert YouTube json3 subtitle format to SRT."""
    data = json.loads(raw)
    entries = []
    for event in data.get('events', []):
        segs = event.get('segs')
        if not segs:
            continue
        text = ''.join(s.get('utf8', '') for s in segs).strip()
        if not text or text == '\n':
            continue
        start = event.get('tStartMs', 0)
        end = start + event.get('dDurationMs', 0)
        entries.append((_ms_to_srt_time(start), _ms_to_srt_time(end), text))
    return '\n\n'.join(f"{i}\n{s} --> {e}\n{t}" for i, (s, e, t) in enumerate(entries, 1))


def _vtt_to_srt(raw: str) -> str:
    """Convert WebVTT (including YouTube word-level timing) to SRT."""
    entries = []
    for block in re.split(r'\n{2,}', raw.strip()):
        lines = block.strip().splitlines()
        # Find the timestamp line
        ts_idx = next(
            (i for i, ln in enumerate(lines) if '-->' in ln and re.search(r'\d{2}:\d{2}', ln)),
            None,
        )
        if ts_idx is None:
            continue
        ts_match = re.search(
            r'(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})',
            lines[ts_idx],
        )
        if not ts_match:
            continue
        start = ts_match.group(1).replace('.', ',')
        end = ts_match.group(2).replace('.', ',')
        text_lines = []
        for ln in lines[ts_idx + 1:]:
            # Strip word-level timing (<00:00:00.000>) and other tags (<c>, <b>, etc.)
            cleaned = re.sub(r'<[^>]+>', '', ln).strip()
            if cleaned:
                text_lines.append(cleaned)
        if text_lines:
            entries.append((start, end, '\n'.join(text_lines)))
    return '\n\n'.join(f"{i}\n{s} --> {e}\n{t}" for i, (s, e, t) in enumerate(entries, 1))


class SubtitleExtractor:
    """Extract English subtitles from YouTube videos."""

    # Preferred English language codes checked first in exact priority order
    ENGLISH_LANGS_PREFERRED = ['en', 'en-US', 'en-GB', 'en-CA', 'en-AU', 'en-IE']

    @classmethod
    def _find_english_lang(cls, track_dict: dict) -> Optional[str]:
        """Return the best English language key in track_dict, or None.

        Checks preferred variants first, then falls back to any key starting
        with 'en' (e.g. en-x-autogen, en-Latn) sorted shortest-first.
        'en-orig' is excluded here — it is handled separately as a translated fallback.
        """
        for lang in cls.ENGLISH_LANGS_PREFERRED:
            if lang in track_dict:
                return lang
        candidates = sorted(
            [k for k in track_dict if k.lower().startswith('en') and k != 'en-orig'],
            key=len
        )
        return candidates[0] if candidates else None

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        cookies_file: Optional[Path] = None,
        cookies_from_browser: Optional[str] = None,
    ):
        self.output_dir = output_dir
        self.cookies_file = cookies_file
        self.cookies_from_browser = cookies_from_browser

    def set_output_dir(self, output_dir: Path):
        """Set output directory for next extraction."""
        self.output_dir = output_dir

    def extract(self, video_url: str) -> SubtitleResult:
        """
        Extract English subtitles for a single video.

        Priority order:
        1. Uploaded English captions
        2. Auto-generated English captions
        3. Translated English captions (en-orig)

        Uses download=False with the ios player client to get the info dict
        (which includes subtitle URLs from the ios player API JSON without
        needing a PO token), then downloads the subtitle URL directly.
        This bypasses yt-dlp's format selection, which would fail because
        all ios video formats require a GVS PO token.
        """
        if self.output_dir is None:
            raise ValueError("output_dir must be set before extraction")

        _UNKNOWN = VideoInfo(video_id="unknown", title="", url=video_url)

        ydl_opts = {
            'quiet': True,
            'no_warnings': False,
            'no_color': True,
            'ignoreerrors': True,
            # ios player client returns automatic caption data in the player
            # API JSON, which is fetched during info extraction (download=False).
            'extractor_args': {
                'youtube': {
                    'player_client': ['ios'],
                },
            },
        }
        if self.cookies_file and self.cookies_file.exists():
            ydl_opts['cookiefile'] = str(self.cookies_file)
        elif self.cookies_from_browser:
            ydl_opts['cookiesfrombrowser'] = (self.cookies_from_browser,)

        try:
            stderr_target = sys.stderr if DEBUG else io.StringIO()
            with contextlib.redirect_stderr(stderr_target):
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # process=False: skip process_ie_result entirely, so format selection
                    # never runs (it would fail because all ios formats need a GVS PO token).
                    # The ios player API JSON — fetched during _real_extract — still populates
                    # automatic_captions with subtitle URLs.
                    info = ydl.extract_info(video_url, download=False, process=False)
        except Exception as e:
            if DEBUG:
                print(f"DEBUG: Exception for {video_url}: {type(e).__name__}: {e}", file=sys.stderr)
            if _is_upcoming_error(str(e)):
                return SubtitleResult(video=_UNKNOWN, success=False, error=UPCOMING_LIVE_ERROR)
            return SubtitleResult(video=_UNKNOWN, success=False, error="Failed to extract video info")

        if info is None:
            # With ignoreerrors=True, yt-dlp reports the error to stderr and
            # returns None; recover the message from the captured stream.
            captured = stderr_target.getvalue() if isinstance(stderr_target, io.StringIO) else ''
            if DEBUG:
                print(f"DEBUG: yt-dlp returned None for {video_url}", file=sys.stderr)
            if _is_upcoming_error(captured):
                return SubtitleResult(video=_UNKNOWN, success=False, error=UPCOMING_LIVE_ERROR)
            return SubtitleResult(video=_UNKNOWN, success=False, error="Failed to extract video info")

        video_id = info.get('id', '')
        video_info = VideoInfo(
            video_id=video_id,
            title=info.get('title', ''),
            url=info.get('webpage_url', video_url),
            upload_date=parse_upload_date(info.get('upload_date')),
            channel_id=info.get('channel_id'),
            channel_title=info.get('channel'),
        )

        subtitles_info = {
            'subtitles': info.get('subtitles', {}),
            'automatic_captions': info.get('automatic_captions', {}),
        }

        if DEBUG:
            print(f"DEBUG: subtitles keys: {list(subtitles_info['subtitles'].keys())}", file=sys.stderr)
            print(f"DEBUG: automatic_captions keys: {list(subtitles_info['automatic_captions'].keys())}", file=sys.stderr)

        subtitle_type, lang_code, is_auto = self._select_best_subtitle(subtitles_info)

        if subtitle_type is None:
            if DEBUG:
                print(f"DEBUG: No English subtitles for {video_id}", file=sys.stderr)
            return SubtitleResult(video=video_info, success=False, error="No English subtitles available")

        track_list = (subtitles_info['automatic_captions' if is_auto else 'subtitles']
                      .get(lang_code, []))

        srt_content = self._fetch_subtitle_as_srt(ydl_opts, track_list, video_id, lang_code)
        if srt_content is None:
            return SubtitleResult(video=video_info, success=False, error="Failed to download subtitle")

        simplified_content = simplify_srt(srt_content)
        final_content = self._add_provenance_header(simplified_content, video_info, subtitle_type)
        output_path = self._save_subtitle(video_info, final_content)

        return SubtitleResult(
            video=video_info,
            success=True,
            subtitle_type=subtitle_type,
            file_path=str(output_path)
        )

    def _fetch_subtitle_as_srt(
        self,
        ydl_opts: dict,
        track_list: list,
        video_id: str,
        lang_code: str,
    ) -> Optional[str]:
        """Download a subtitle track URL and return the content as SRT text."""
        if not track_list:
            return None

        # Prefer json3 (YouTube native, lossless), then vtt, then anything
        preferred = ('json3', 'vtt', 'srv3', 'srv2', 'srv1', 'ttml')
        url = ext = None
        for pref in preferred:
            for track in track_list:
                if track.get('ext') == pref:
                    url, ext = track['url'], pref
                    break
            if url:
                break
        if url is None and track_list:
            url = track_list[0]['url']
            ext = track_list[0].get('ext', 'json3')

        try:
            stderr_target = sys.stderr if DEBUG else io.StringIO()
            with contextlib.redirect_stderr(stderr_target):
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    raw = ydl.urlopen(url).read().decode('utf-8')
            if ext == 'json3':
                return _json3_to_srt(raw)
            else:
                return _vtt_to_srt(raw)
        except Exception as e:
            if DEBUG:
                print(f"DEBUG: Failed to fetch subtitle {video_id}/{lang_code}: {type(e).__name__}: {e}",
                      file=sys.stderr)
            return None

    def _get_video_info(self, url: str) -> tuple[Optional[VideoInfo], Optional[dict]]:
        """Extract video metadata and subtitle info without downloading."""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            # Required so yt-dlp fetches subtitle metadata from YouTube's API.
            # Without these, recent yt-dlp versions skip the caption manifest
            # requests entirely, returning empty subtitles/automatic_captions dicts.
            'writesubtitles': True,
            'writeautomaticsub': True,
        }
        if self.cookies_file and self.cookies_file.exists():
            ydl_opts['cookiefile'] = str(self.cookies_file)
        elif self.cookies_from_browser:
            ydl_opts['cookiesfrombrowser'] = (self.cookies_from_browser,)
        try:
            # Suppress stderr output to hide yt-dlp errors
            with contextlib.redirect_stderr(io.StringIO()):
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    if info is None:
                        return None, None
                    video_info = VideoInfo(
                        video_id=info.get('id', ''),
                        title=info.get('title', ''),
                        url=info.get('webpage_url', url),
                        upload_date=parse_upload_date(info.get('upload_date')),
                        channel_id=info.get('channel_id'),
                        channel_title=info.get('channel'),
                    )
                    subtitles_info = {
                        'subtitles': info.get('subtitles', {}),
                        'automatic_captions': info.get('automatic_captions', {}),
                    }
                    return video_info, subtitles_info
        except Exception as e:
            if DEBUG:
                print(f"DEBUG: Exception in _get_video_info for {url}: {type(e).__name__}: {e}", file=sys.stderr)
            return None, None

    def _select_best_subtitle(
        self, subtitles_info: Optional[dict]
    ) -> tuple[Optional[SubtitleType], Optional[str], bool]:
        """
        Determine best available English subtitle.

        Returns (SubtitleType, language_code, is_automatic) or (None, None, False).
        """
        if subtitles_info is None:
            return None, None, False

        subtitles = subtitles_info.get('subtitles', {})
        automatic_captions = subtitles_info.get('automatic_captions', {})

        # Priority 1: Uploaded English (any en* variant)
        lang = self._find_english_lang(subtitles)
        if lang is not None:
            return SubtitleType.UPLOADED, lang, False

        # Priority 2: Auto-generated English (any en* variant)
        lang = self._find_english_lang(automatic_captions)
        if lang is not None:
            return SubtitleType.AUTO_GENERATED, lang, True

        # Priority 3: 'en-orig' indicates translated captions
        if 'en-orig' in automatic_captions:
            return SubtitleType.TRANSLATED, 'en-orig', True
        if 'en-orig' in subtitles:
            return SubtitleType.TRANSLATED, 'en-orig', False

        return None, None, False

    def _download_subtitle(
        self, url: str, lang: str, is_auto: bool
    ) -> Optional[str]:
        """Download subtitle content as SRT format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_template = str(Path(tmpdir) / '%(id)s.%(ext)s')

            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'writesubtitles': not is_auto,
                'writeautomaticsub': is_auto,
                'subtitleslangs': [lang],
                'subtitlesformat': 'srt',
                'outtmpl': output_template,
                'ignoreerrors': False,  # Changed from True to actually catch errors
                'no_color': True,
                # Add headers to appear more like a browser
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-us,en;q=0.5',
                    'Sec-Fetch-Mode': 'navigate',
                }
            }
            if self.cookies_file and self.cookies_file.exists():
                ydl_opts['cookiefile'] = str(self.cookies_file)
            elif self.cookies_from_browser:
                ydl_opts['cookiesfrombrowser'] = (self.cookies_from_browser,)

            try:
                # Suppress stderr output to hide HTTP 403 and other yt-dlp errors
                # (unless debug mode is enabled)
                stderr_target = sys.stderr if DEBUG else io.StringIO()
                with contextlib.redirect_stderr(stderr_target):
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        if info is None:
                            if DEBUG:
                                print(f"DEBUG: yt-dlp returned None for {url}", file=sys.stderr)
                            return None

                        video_id = info.get('id', '')

                        # Find the downloaded subtitle file
                        srt_path = Path(tmpdir) / f'{video_id}.{lang}.srt'
                        if srt_path.exists():
                            return srt_path.read_text(encoding='utf-8')

                        # Try without language code in filename
                        for f in Path(tmpdir).glob('*.srt'):
                            return f.read_text(encoding='utf-8')

                        if DEBUG:
                            print(f"DEBUG: No .srt files found in {tmpdir} for video {video_id}", file=sys.stderr)
                            print(f"  Files present: {list(Path(tmpdir).glob('*'))}", file=sys.stderr)
                        return None
            except Exception as e:
                if DEBUG:
                    print(f"DEBUG: Exception in _download_subtitle for {url}: {type(e).__name__}: {e}", file=sys.stderr)
                return None

    def _add_provenance_header(
        self, srt_content: str, video: VideoInfo, sub_type: SubtitleType
    ) -> str:
        """Add metadata header to SRT file per spec."""
        upload_date_str = video.upload_date.isoformat() if video.upload_date else 'Unknown'
        header = f"""# Video: {video.title}
# URL: {video.url}
# Video ID: {video.video_id}
# Publish Date: {upload_date_str}
# Subtitle Type: {sub_type.value}
# Downloaded: {date.today().isoformat()}

"""
        return header + srt_content

    def _save_subtitle(self, video: VideoInfo, content: str) -> Path:
        """Save subtitle with spec-compliant filename."""
        filename = self._generate_filename(video)
        output_path = self.output_dir / filename
        output_path.write_text(content, encoding='utf-8')
        return output_path

    def _generate_filename(self, video: VideoInfo) -> str:
        """Generate filename: YYYY-MM-DD - <sanitized title> [VIDEO_ID].txt"""
        date_prefix = video.upload_date.isoformat() if video.upload_date else "0000-00-00"
        safe_title = sanitize_filename(video.title)
        return f"{date_prefix} - {safe_title} [{video.video_id}].txt"
