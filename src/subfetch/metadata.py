"""Channel metadata management for subfetch."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class ChannelMetadata:
    """Metadata stored in channel folder."""
    channel_id: str
    channel_title: str
    channel_url: str
    created_date: str  # ISO format timestamp
    last_updated: str  # ISO format timestamp
    total_videos_archived: int


class MetadataManager:
    """Manage .channel_metadata.json files."""

    @staticmethod
    def get_metadata_path(channel_folder: Path) -> Path:
        """Returns channel_folder / .channel_metadata.json"""
        return channel_folder / '.channel_metadata.json'

    @staticmethod
    def create(
        channel_folder: Path,
        channel_id: str,
        channel_title: str,
        channel_url: str
    ) -> ChannelMetadata:
        """
        Create new channel metadata file.

        Returns the created ChannelMetadata object.
        """
        now = datetime.now().isoformat()
        metadata = ChannelMetadata(
            channel_id=channel_id,
            channel_title=channel_title,
            channel_url=channel_url,
            created_date=now,
            last_updated=now,
            total_videos_archived=0
        )

        MetadataManager._save(channel_folder, metadata)
        return metadata

    @staticmethod
    def load(channel_folder: Path) -> Optional[ChannelMetadata]:
        """
        Load existing metadata.

        Returns None if metadata file doesn't exist.
        """
        metadata_path = MetadataManager.get_metadata_path(channel_folder)

        if not metadata_path.exists():
            return None

        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return ChannelMetadata(**data)
        except (json.JSONDecodeError, TypeError, KeyError):
            return None

    @staticmethod
    def update(channel_folder: Path, videos_added: int = 0):
        """
        Update last_updated timestamp and optionally increment video count.

        Creates metadata file if it doesn't exist.
        """
        metadata = MetadataManager.load(channel_folder)

        if metadata is None:
            # If no metadata exists, we can't update it properly
            # This shouldn't happen in normal operation
            return

        metadata.last_updated = datetime.now().isoformat()
        if videos_added > 0:
            metadata.total_videos_archived += videos_added

        MetadataManager._save(channel_folder, metadata)

    @staticmethod
    def _save(channel_folder: Path, metadata: ChannelMetadata):
        """Internal: Save metadata to disk."""
        metadata_path = MetadataManager.get_metadata_path(channel_folder)
        channel_folder.mkdir(parents=True, exist_ok=True)

        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(metadata), f, indent=2, ensure_ascii=False)
