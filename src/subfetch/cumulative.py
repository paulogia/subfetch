"""Cumulative transcript file management for subfetch."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

from .utils import sanitize_filename


class CumulativeManager:
    """Manages cumulative transcript files for a channel."""

    MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
    SEPARATOR = "=" * 80 + "\n"

    @staticmethod
    def append_transcripts(
        channel_folder: Path,
        channel_title: str,
        transcript_paths: List[Path]
    ) -> Optional[Path]:
        """
        Append newly downloaded transcripts to cumulative file.

        Args:
            channel_folder: Path to channel's folder
            channel_title: Display name for the channel
            transcript_paths: List of .txt files to append

        Returns:
            Path to the cumulative file written, or None if no files appended
        """
        if not transcript_paths:
            return None

        # Sanitize channel title for filename
        safe_title = sanitize_filename(channel_title, max_length=80)

        # Find current cumulative file
        current_file, current_number = CumulativeManager.find_current_cumulative(
            channel_folder, safe_title
        )

        if current_file is None:
            # Create first cumulative file
            current_number = 1
            current_file = CumulativeManager.create_next_cumulative(
                channel_folder, safe_title, current_number
            )

        # Append each transcript
        for transcript_path in transcript_paths:
            # Read entire transcript content
            content = transcript_path.read_text(encoding='utf-8')

            # Prepare content with separator
            # Add separator before content unless file is empty
            if current_file.exists() and current_file.stat().st_size > 0:
                content_to_append = CumulativeManager.SEPARATOR + content
            else:
                content_to_append = content  # First entry, no separator

            # Check size limit
            if CumulativeManager.would_exceed_limit(current_file, content_to_append):
                # Create next cumulative file
                current_number += 1
                current_file = CumulativeManager.create_next_cumulative(
                    channel_folder, safe_title, current_number
                )
                content_to_append = content  # No separator for new file

            # Append to current file
            with open(current_file, 'a', encoding='utf-8') as f:
                f.write(content_to_append)

        return current_file

    @staticmethod
    def find_current_cumulative(
        channel_folder: Path,
        channel_title: str
    ) -> tuple[Optional[Path], int]:
        """
        Find the current (highest numbered) cumulative file.

        Args:
            channel_folder: Path to channel's folder
            channel_title: Sanitized channel title

        Returns:
            (path_to_file, file_number) or (None, 0) if none exist
        """
        pattern = f"{channel_title}-*.txt"
        cumulative_files = []

        for file in channel_folder.glob(pattern):
            # Extract number using regex: ChannelName-001.txt
            match = re.search(r'-(\d{3})\.txt$', file.name)
            if match:
                number = int(match.group(1))
                cumulative_files.append((file, number))

        if not cumulative_files:
            return None, 0

        # Return the file with highest number
        return max(cumulative_files, key=lambda x: x[1])

    @staticmethod
    def would_exceed_limit(file_path: Path, content_to_append: str) -> bool:
        """
        Check if appending content would exceed 10MB limit.

        Args:
            file_path: Path to cumulative file
            content_to_append: Content to append

        Returns:
            True if would exceed limit, False otherwise
        """
        try:
            current_size = file_path.stat().st_size if file_path.exists() else 0
            append_size = len(content_to_append.encode('utf-8'))
            return (current_size + append_size) > CumulativeManager.MAX_SIZE_BYTES
        except OSError:
            # If we can't determine size, assume it would exceed (safe default)
            return True

    @staticmethod
    def create_next_cumulative(
        channel_folder: Path,
        channel_title: str,
        number: int
    ) -> Path:
        """
        Create a new cumulative file with the given number.

        Args:
            channel_folder: Path to channel's folder
            channel_title: Sanitized channel title
            number: File number (e.g., 1 for 001)

        Returns:
            Path to the newly created file
        """
        filename = f"{channel_title}-{number:03d}.txt"
        file_path = channel_folder / filename
        # Create empty file if it doesn't exist
        file_path.touch(exist_ok=True)
        return file_path
