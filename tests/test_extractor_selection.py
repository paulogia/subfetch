"""Tests for English caption track selection."""

from subfetch.extractor import SubtitleExtractor, _is_age_restricted
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


class TestAgeGateDetection:
    def test_matches_youtube_age_gate_messages(self):
        assert _is_age_restricted('ERROR: [youtube] abc: Sorry, this content is age-restricted')
        assert _is_age_restricted('Sign in to confirm your age')

    def test_ignores_unrelated_failures(self):
        assert not _is_age_restricted('ERROR: [youtube] abc: Video unavailable')
        assert not _is_age_restricted('')


class TestAgeGateRetry:
    def _extractor(self, tmp_path):
        cookies = tmp_path / 'cookies.txt'
        cookies.write_text('# Netscape HTTP Cookie File\n')
        return SubtitleExtractor(output_dir=tmp_path, cookies_file=cookies)

    def test_retries_age_gated_video_on_mweb(self, tmp_path, monkeypatch):
        calls = []

        def fake(self, url, opts):
            calls.append(opts.get('extractor_args'))
            if len(calls) == 1:
                return None, 'ERROR: Sorry, this content is age-restricted'
            return None, 'ERROR: Video unavailable'

        monkeypatch.setattr(SubtitleExtractor, '_extract_info', fake)
        self._extractor(tmp_path).extract('https://www.youtube.com/watch?v=abc')

        assert len(calls) == 2
        assert calls[1] == {'youtube': {'player_client': ['mweb']}}

    def test_no_retry_for_other_failures(self, tmp_path, monkeypatch):
        calls = []

        def fake(self, url, opts):
            calls.append(opts)
            return None, 'ERROR: Video unavailable'

        monkeypatch.setattr(SubtitleExtractor, '_extract_info', fake)
        result = self._extractor(tmp_path).extract('https://www.youtube.com/watch?v=abc')

        assert len(calls) == 1
        assert result.error == 'Failed to extract video info'

    def test_no_retry_without_cookies(self, tmp_path, monkeypatch):
        calls = []

        def fake(self, url, opts):
            calls.append(opts)
            return None, 'ERROR: Sorry, this content is age-restricted'

        monkeypatch.setattr(SubtitleExtractor, '_extract_info', fake)
        SubtitleExtractor(output_dir=tmp_path).extract('https://www.youtube.com/watch?v=abc')

        assert len(calls) == 1
