"""Tests for utility functions."""

from datetime import date

from subfetch.utils import parse_upload_date, sanitize_filename


class TestSanitizeFilename:
    def test_removes_illegal_chars(self):
        assert sanitize_filename('Test: A/B\\C') == 'Test ABC'

    def test_removes_question_marks(self):
        assert sanitize_filename('What is this?') == 'What is this'

    def test_removes_quotes(self):
        assert sanitize_filename('Say "Hello"') == 'Say Hello'

    def test_collapses_whitespace(self):
        assert sanitize_filename('Too   many   spaces') == 'Too many spaces'

    def test_truncates_long_titles(self):
        long_title = "A" * 200
        result = sanitize_filename(long_title, max_length=100)
        assert len(result) <= 100

    def test_truncates_at_word_boundary(self):
        title = "This is a somewhat long title that needs truncation"
        result = sanitize_filename(title, max_length=30)
        assert len(result) <= 30
        assert not result.endswith(' ')

    def test_handles_empty_input(self):
        assert sanitize_filename('') == 'untitled'

    def test_handles_all_invalid_chars(self):
        assert sanitize_filename('???:::') == 'untitled'

    def test_preserves_valid_chars(self):
        assert sanitize_filename('Hello World 123') == 'Hello World 123'


class TestParseUploadDate:
    def test_parses_valid_date(self):
        assert parse_upload_date('20231225') == date(2023, 12, 25)

    def test_parses_january(self):
        assert parse_upload_date('20240101') == date(2024, 1, 1)

    def test_returns_none_for_none(self):
        assert parse_upload_date(None) is None

    def test_returns_none_for_empty_string(self):
        assert parse_upload_date('') is None

    def test_returns_none_for_invalid_format(self):
        assert parse_upload_date('2023-12-25') is None

    def test_returns_none_for_short_string(self):
        assert parse_upload_date('2023') is None

    def test_returns_none_for_invalid_date(self):
        assert parse_upload_date('20231332') is None  # Invalid month/day
