"""Subtitle extraction using yt-dlp."""

from __future__ import annotations

import contextlib
import io
import tempfile
from datetime import date
from pathlib import Path
from typing import Optional

import yt_dlp

from .models import SubtitleResult, SubtitleType, VideoInfo
from .transform import simplify_srt
from .utils import parse_upload_date, sanitize_filename


class SubtitleExtractor:
    """Extract English subtitles from YouTube videos."""

    # English language variants in priority order
    ENGLISH_LANGS = ['en', 'en-US', 'en-GB', 'en-CA', 'en-AU', 'en-IE']

    def __init__(self, output_dir: Optional[Path] = None, cookies_file: Optional[Path] = None):
        self.output_dir = output_dir
        self.cookies_file = cookies_file

    def set_output_dir(self, output_dir: Path):
        """Set output directory for next extraction."""
        self.output_dir = output_dir

    def extract(self, video_url: str) -> SubtitleResult:
        """
        Extract English subtitles for a single video.

        Priority order per spec:
        1. Uploaded English captions
        2. Auto-generated English captions
        3. Translated English captions
        """
        if self.output_dir is None:
            raise ValueError("output_dir must be set before extraction")

        # Step 1: Get video info and available subtitles
        video_info, subtitles_info = self._get_video_info(video_url)
        if video_info is None:
            return SubtitleResult(
                video=VideoInfo(video_id="unknown", title="", url=video_url),
                success=False,
                error="Failed to extract video info"
            )

        # Step 2: Determine best subtitle source
        subtitle_type, lang_code, is_auto = self._select_best_subtitle(subtitles_info)
        if subtitle_type is None:
            return SubtitleResult(
                video=video_info,
                success=False,
                error="No English subtitles available"
            )

        # Step 3: Download subtitle file
        srt_content = self._download_subtitle(video_url, lang_code, is_auto)
        if srt_content is None:
            return SubtitleResult(
                video=video_info,
                success=False,
                error="Failed to download subtitle"
            )

        # Step 4: Transform SRT to simplified format
        simplified_content = simplify_srt(srt_content)

        # Step 5: Add provenance header and save
        final_content = self._add_provenance_header(simplified_content, video_info, subtitle_type)
        output_path = self._save_subtitle(video_info, final_content)

        return SubtitleResult(
            video=video_info,
            success=True,
            subtitle_type=subtitle_type,
            file_path=str(output_path)
        )

    def _get_video_info(self, url: str) -> tuple[Optional[VideoInfo], Optional[dict]]:
        """Extract video metadata and subtitle info without downloading."""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
        }
        if self.cookies_file and self.cookies_file.exists():
            ydl_opts['cookiefile'] = str(self.cookies_file)
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

        # Priority 1: Uploaded English
        for lang in self.ENGLISH_LANGS:
            if lang in subtitles:
                return SubtitleType.UPLOADED, lang, False

        # Priority 2: Auto-generated English
        for lang in self.ENGLISH_LANGS:
            if lang in automatic_captions:
                return SubtitleType.AUTO_GENERATED, lang, True

        # Priority 3: Check for 'en-orig' which indicates translated
        if 'en-orig' in automatic_captions:
            return SubtitleType.TRANSLATED, 'en-orig', True

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
                'ignoreerrors': True,
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

            try:
                # Suppress stderr output to hide HTTP 403 and other yt-dlp errors
                with contextlib.redirect_stderr(io.StringIO()):
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        video_id = info.get('id', '')

                        # Find the downloaded subtitle file
                        srt_path = Path(tmpdir) / f'{video_id}.{lang}.srt'
                        if srt_path.exists():
                            return srt_path.read_text(encoding='utf-8')

                        # Try without language code in filename
                        for f in Path(tmpdir).glob('*.srt'):
                            return f.read_text(encoding='utf-8')

                        return None
            except Exception:
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
