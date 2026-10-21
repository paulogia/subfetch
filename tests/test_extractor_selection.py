"""Tests for English caption track selection."""

from subfetch.extractor import SubtitleExtractor
from subfetch.models import SubtitleType


def _track(lang, translated=False, ext='json3'):
    url = f'https://www.youtube.com/api/timedtext?v=abc&lang={lang}&fmt={ext}'
    if translated:
        url += '&tlang=en&variant=punctuated'
    return {'ext': ext, 'url': url}


class TestSelectBestSubtitle:
    def test_prefers_original_over_translated_en_alias(self):
        info = {
            'subtitles': {},
            'automatic_captions': {
                'en': [_track('en', translated=True)],
                'en-orig': [_track('en')],
            },
        }
        assert SubtitleExtractor()._select_best_subtitle(info) == (
            SubtitleType.AUTO_GENERATED, 'en-orig', True
        )

    def test_keeps_plain_en_when_not_translated(self):
        info = {
            'subtitles': {},
            'automatic_captions': {
                'en': [_track('en')],
                'en-orig': [_track('en')],
            },
        }
        assert SubtitleExtractor()._select_best_subtitle(info) == (
            SubtitleType.AUTO_GENERATED, 'en', True
        )

    def test_en_orig_alone_counts_as_auto_generated(self):
        info = {'subtitles': {}, 'automatic_captions': {'en-orig': [_track('en')]}}
        assert SubtitleExtractor()._select_best_subtitle(info) == (
            SubtitleType.AUTO_GENERATED, 'en-orig', True
        )

    def test_uploaded_wins_over_automatic(self):
        info = {
            'subtitles': {'en': [_track('en')]},
            'automatic_captions': {'en': [_track('en')]},
        }
        assert SubtitleExtractor()._select_best_subtitle(info) == (
            SubtitleType.UPLOADED, 'en', False
        )

    def test_no_english_returns_nothing(self):
        info = {'subtitles': {}, 'automatic_captions': {'ko': [_track('ko')]}}
        assert SubtitleExtractor()._select_best_subtitle(info) == (None, None, False)
