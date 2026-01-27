"""Transform SRT subtitle format to simplified timestamp-prefixed text."""

from __future__ import annotations

import re


def simplify_srt(srt_content: str) -> str:
    """
    Transform SRT format to simplified timestamp-prefixed text.

    Converts:
        1
        00:00:01,000 --> 00:00:03,000
        Hello world

        2
        00:00:03,500 --> 00:00:05,000
        How are you

    To:
        00:00:01 Hello world
        00:00:03 How are you

    Args:
        srt_content: Raw SRT subtitle content

    Returns:
        Simplified timestamp-prefixed text
    """
    # Normalize line endings to LF
    content = srt_content.replace('\r\n', '\n').replace('\r', '\n')

    # Collapse multiple blank lines to single blank line
    content = re.sub(r'\n+', '\n', content)

    # Transform: sequence_number\ntimestamp --> endtime\ntext
    # Into: HH:MM:SS text
    # Pattern: number line + timestamp line -> "HH:MM:SS " prefix
    content = re.sub(
        r'^\d+\n(\d{2}:\d{2}:\d{2}).*\n',
        r'\1 ',
        content,
        flags=re.MULTILINE
    )

    return content
