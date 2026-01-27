"""Tests for cumulative transcript file management."""

import pytest
from pathlib import Path

from subfetch.cumulative import CumulativeManager


class TestFindCurrentCumulative:
    """Tests for finding the current cumulative file."""

    def test_finds_highest_numbered_file(self, tmp_path):
        """Should find the file with the highest number."""
        # Create test files
        (tmp_path / "TestChannel-001.txt").touch()
        (tmp_path / "TestChannel-002.txt").touch()
        (tmp_path / "TestChannel-003.txt").touch()

        file, number = CumulativeManager.find_current_cumulative(
            tmp_path, "TestChannel"
        )

        assert number == 3
        assert file.name == "TestChannel-003.txt"

    def test_returns_none_when_no_files(self, tmp_path):
        """Should return (None, 0) when no cumulative files exist."""
        file, number = CumulativeManager.find_current_cumulative(
            tmp_path, "TestChannel"
        )

        assert file is None
        assert number == 0

    def test_ignores_individual_transcript_files(self, tmp_path):
        """Should not match individual transcript files."""
        # Create individual transcript (should be ignored)
        (tmp_path / "2024-01-01 - Test Video [abc123].txt").touch()

        file, number = CumulativeManager.find_current_cumulative(
            tmp_path, "TestChannel"
        )

        assert file is None
        assert number == 0

    def test_handles_gaps_in_numbering(self, tmp_path):
        """Should find max number even with gaps."""
        (tmp_path / "TestChannel-001.txt").touch()
        (tmp_path / "TestChannel-005.txt").touch()  # Gap in numbering

        file, number = CumulativeManager.find_current_cumulative(
            tmp_path, "TestChannel"
        )

        assert number == 5
        assert file.name == "TestChannel-005.txt"


class TestWouldExceedLimit:
    """Tests for size limit checking."""

    def test_empty_file_under_limit(self, tmp_path):
        """Small content in empty file should not exceed limit."""
        file = tmp_path / "test.txt"
        file.touch()

        content = "x" * 100  # 100 bytes
        assert not CumulativeManager.would_exceed_limit(file, content)

    def test_near_limit_detection(self, tmp_path):
        """Should detect when appending would exceed 10MB."""
        file = tmp_path / "test.txt"

        # Write 9.5 MB
        file.write_text("x" * (9 * 1024 * 1024 + 512 * 1024))

        # Try to add 1 MB (would exceed)
        content = "x" * (1 * 1024 * 1024)
        assert CumulativeManager.would_exceed_limit(file, content)

    def test_exactly_at_limit(self, tmp_path):
        """Should not exceed when exactly at limit."""
        file = tmp_path / "test.txt"

        # Write exactly 10MB
        file.write_text("x" * (10 * 1024 * 1024))

        # Try to add 1 byte (would exceed)
        content = "x"
        assert CumulativeManager.would_exceed_limit(file, content)

    def test_nonexistent_file_treated_as_empty(self, tmp_path):
        """Non-existent file should be treated as size 0."""
        file = tmp_path / "nonexistent.txt"

        content = "x" * 100
        assert not CumulativeManager.would_exceed_limit(file, content)


class TestCreateNextCumulative:
    """Tests for creating new cumulative files."""

    def test_creates_file_with_correct_name(self, tmp_path):
        """Should create file with correct naming format."""
        result = CumulativeManager.create_next_cumulative(
            tmp_path, "TestChannel", 1
        )

        assert result.name == "TestChannel-001.txt"
        assert result.exists()

    def test_creates_file_with_padding(self, tmp_path):
        """Should pad number to 3 digits."""
        result = CumulativeManager.create_next_cumulative(
            tmp_path, "TestChannel", 42
        )

        assert result.name == "TestChannel-042.txt"
        assert result.exists()

    def test_creates_file_with_large_number(self, tmp_path):
        """Should handle large file numbers."""
        result = CumulativeManager.create_next_cumulative(
            tmp_path, "TestChannel", 999
        )

        assert result.name == "TestChannel-999.txt"
        assert result.exists()


class TestAppendTranscripts:
    """Tests for appending transcripts to cumulative files."""

    def test_creates_first_cumulative_file(self, tmp_path):
        """Should create first cumulative file when none exist."""
        # Create sample transcript
        transcript = tmp_path / "2024-01-01 - Test [abc123].txt"
        transcript.write_text("# Video: Test\n\n00:00:01 Hello world")

        result = CumulativeManager.append_transcripts(
            tmp_path,
            "TestChannel",
            [transcript]
        )

        assert result is not None
        assert result.name == "TestChannel-001.txt"
        assert result.exists()

        # Verify content
        content = result.read_text()
        assert "Hello world" in content

    def test_appends_to_existing_cumulative(self, tmp_path):
        """Should append to existing cumulative file."""
        # Create existing cumulative
        cumulative = tmp_path / "TestChannel-001.txt"
        cumulative.write_text("First video content")

        # Create new transcript
        transcript = tmp_path / "2024-01-02 - Test2 [def456].txt"
        transcript.write_text("Second video content")

        CumulativeManager.append_transcripts(
            tmp_path,
            "TestChannel",
            [transcript]
        )

        content = cumulative.read_text()
        assert "First video content" in content
        assert CumulativeManager.SEPARATOR in content
        assert "Second video content" in content

    def test_adds_separator_between_videos(self, tmp_path):
        """Should add separator line between videos."""
        # Create first transcript
        transcript1 = tmp_path / "2024-01-01 - Test1 [abc123].txt"
        transcript1.write_text("Video 1 content")

        # Create second transcript
        transcript2 = tmp_path / "2024-01-02 - Test2 [def456].txt"
        transcript2.write_text("Video 2 content")

        CumulativeManager.append_transcripts(
            tmp_path,
            "TestChannel",
            [transcript1, transcript2]
        )

        cumulative = tmp_path / "TestChannel-001.txt"
        content = cumulative.read_text()

        # Should have exactly one separator
        assert content.count(CumulativeManager.SEPARATOR) == 1
        assert "Video 1 content" in content
        assert "Video 2 content" in content

    def test_creates_new_file_when_size_exceeded(self, tmp_path):
        """Should create new file when size limit exceeded."""
        # Create existing cumulative near limit
        cumulative = tmp_path / "TestChannel-001.txt"
        cumulative.write_text("x" * (10 * 1024 * 1024 - 1000))  # Almost 10MB

        # Create transcript that would exceed
        transcript = tmp_path / "2024-01-02 - Test [def456].txt"
        transcript.write_text("y" * 10000)

        result = CumulativeManager.append_transcripts(
            tmp_path,
            "TestChannel",
            [transcript]
        )

        # Should create new file
        assert result.name == "TestChannel-002.txt"
        assert (tmp_path / "TestChannel-001.txt").exists()
        assert (tmp_path / "TestChannel-002.txt").exists()

        # New file should have the new content
        new_content = result.read_text()
        assert "y" * 10000 in new_content

    def test_handles_multiple_transcripts(self, tmp_path):
        """Should handle appending multiple transcripts at once."""
        transcripts = []
        for i in range(5):
            transcript = tmp_path / f"2024-01-0{i+1} - Test{i} [abc{i}].txt"
            transcript.write_text(f"Video {i} content")
            transcripts.append(transcript)

        CumulativeManager.append_transcripts(
            tmp_path,
            "TestChannel",
            transcripts
        )

        cumulative = tmp_path / "TestChannel-001.txt"
        content = cumulative.read_text()

        # All videos should be present
        for i in range(5):
            assert f"Video {i} content" in content

        # Should have 4 separators (between 5 videos)
        assert content.count(CumulativeManager.SEPARATOR) == 4

    def test_returns_none_for_empty_list(self, tmp_path):
        """Should return None when given empty transcript list."""
        result = CumulativeManager.append_transcripts(
            tmp_path,
            "TestChannel",
            []
        )

        assert result is None

    def test_preserves_full_content_with_headers(self, tmp_path):
        """Should preserve provenance headers in cumulative file."""
        # Create transcript with full header
        transcript = tmp_path / "2024-01-01 - Test [abc123].txt"
        full_content = """# Video: Test Video Title
# URL: https://youtube.com/watch?v=abc123
# Video ID: abc123
# Publish Date: 2024-01-01
# Subtitle Type: auto-generated
# Downloaded: 2024-01-26

00:00:01 Hello world
00:00:05 This is a test
"""
        transcript.write_text(full_content)

        CumulativeManager.append_transcripts(
            tmp_path,
            "TestChannel",
            [transcript]
        )

        cumulative = tmp_path / "TestChannel-001.txt"
        content = cumulative.read_text()

        # All header fields should be preserved
        assert "# Video: Test Video Title" in content
        assert "# URL: https://youtube.com/watch?v=abc123" in content
        assert "# Video ID: abc123" in content
        assert "00:00:01 Hello world" in content

    def test_handles_channel_title_sanitization(self, tmp_path):
        """Should sanitize channel titles for filenames."""
        # Channel title with special characters
        transcript = tmp_path / "2024-01-01 - Test [abc123].txt"
        transcript.write_text("Test content")

        # Title with illegal filename characters
        result = CumulativeManager.append_transcripts(
            tmp_path,
            "Test/Channel:Name?",
            [transcript]
        )

        # Should create a valid filename
        assert result is not None
        assert result.exists()
        # Sanitized version should not contain illegal chars
        assert "/" not in result.name
        assert ":" not in result.name
        assert "?" not in result.name
