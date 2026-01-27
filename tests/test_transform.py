"""Tests for SRT transformation."""

from subfetch.transform import simplify_srt


def test_simplify_srt_basic():
    """Test basic SRT to simplified format conversion."""
    srt_input = """1
00:00:01,000 --> 00:00:03,000
Hello world

2
00:00:03,500 --> 00:00:05,000
How are you

3
00:00:06,000 --> 00:00:08,500
This is a test
"""

    expected = """00:00:01 Hello world
00:00:03 How are you
00:00:06 This is a test
"""

    result = simplify_srt(srt_input)
    assert result == expected


def test_simplify_srt_with_crlf():
    """Test that CRLF line endings are normalized."""
    srt_input = "1\r\n00:00:01,000 --> 00:00:03,000\r\nHello world\r\n"

    result = simplify_srt(srt_input)
    assert result == "00:00:01 Hello world\n"


def test_simplify_srt_collapses_blank_lines():
    """Test that multiple blank lines are collapsed."""
    srt_input = """1
00:00:01,000 --> 00:00:03,000
Hello


2
00:00:03,500 --> 00:00:05,000
World
"""

    result = simplify_srt(srt_input)
    # Should collapse the double newline
    assert "\n\n\n" not in result
    assert "00:00:01 Hello" in result
    assert "00:00:03 World" in result


def test_simplify_srt_multiline_text():
    """Test SRT entries with multi-line text."""
    srt_input = """1
00:00:01,000 --> 00:00:03,000
First line
Second line

2
00:00:03,500 --> 00:00:05,000
Next entry
"""

    result = simplify_srt(srt_input)
    assert "00:00:01 First line" in result
    assert "Second line" in result
    assert "00:00:03 Next entry" in result


def test_simplify_srt_preserves_text_after_timestamp():
    """Test that text content is preserved correctly."""
    srt_input = """1
00:00:01,234 --> 00:00:03,456
Some important text here

2
00:00:05,678 --> 00:00:07,890
More text
"""

    result = simplify_srt(srt_input)
    assert "Some important text here" in result
    assert "More text" in result
    # Timestamps should be simplified (no milliseconds)
    assert "00:00:01 Some" in result
    assert "00:00:05 More" in result
