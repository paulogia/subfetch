"""Configuration and state management for subfetch."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Optional

from .utils import ensure_unique_folder_name, sanitize_filename


@dataclass
class ChannelConfig:
    """Per-channel or per-playlist tracking information."""
    channel_id: str
    channel_title: str
    channel_url: str
    folder_name: str
    added_date: str  # ISO format
    category: str = "main"  # "main" or "skeptical"
    source_type: str = "channel"  # "channel" or "playlist"
    owner_channel_id: Optional[str] = None  # For playlists: creator's channel ID
    owner_channel_name: Optional[str] = None  # For playlists: creator's channel name
    include_lives: bool = False  # Download subtitles for live stream replays


@dataclass
class ArchiveConfig:
    """Master archive configuration."""
    version: str
    root_path: str
    channels: dict[str, ChannelConfig]  # channel_id -> ChannelConfig
    compilations_folder: str = "_compilations"  # Folder for main channels
    compilations_folder_skeptical: str = "_compilations_skeptical"  # Folder for skeptical channels
    auto_update_links: bool = False  # Auto-update symlinks after sync

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'version': self.version,
            'root_path': self.root_path,
            'channels': {
                channel_id: asdict(channel_config)
                for channel_id, channel_config in self.channels.items()
            },
            'compilations_folder': self.compilations_folder,
            'compilations_folder_skeptical': self.compilations_folder_skeptical,
            'auto_update_links': self.auto_update_links
        }

    @staticmethod
    def from_dict(data: dict) -> ArchiveConfig:
        """Load from dictionary after JSON deserialization."""
        channels = {
            channel_id: ChannelConfig(**channel_data)
            for channel_id, channel_data in data.get('channels', {}).items()
        }
        return ArchiveConfig(
            version=data.get('version', '1.0'),
            root_path=data['root_path'],
            channels=channels,
            compilations_folder=data.get('compilations_folder', '_compilations'),
            compilations_folder_skeptical=data.get('compilations_folder_skeptical', '_compilations_skeptical'),
            auto_update_links=data.get('auto_update_links', False)
        )


class ConfigManager:
    """Manages .subfetch/config.json lifecycle."""

    CONFIG_VERSION = '1.0'

    @staticmethod
    def get_config_path(root_path: Path) -> Path:
        """Returns root_path / .subfetch / config.json"""
        return root_path / '.subfetch' / 'config.json'

    @staticmethod
    def init_archive(root_path: Path) -> ArchiveConfig:
        """
        Initialize new archive at root_path.

        Creates .subfetch directory and empty config.json.
        Raises FileExistsError if archive already initialized.
        """
        config_path = ConfigManager.get_config_path(root_path)

        if config_path.exists():
            raise FileExistsError(f"Archive already initialized at {root_path}")

        # Create root and .subfetch directory
        root_path.mkdir(parents=True, exist_ok=True)
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Create initial config
        config = ArchiveConfig(
            version=ConfigManager.CONFIG_VERSION,
            root_path=str(root_path.absolute()),
            channels={}
        )

        ConfigManager.save_archive(config)
        return config

    @staticmethod
    def reinit_archive(root_path: Path) -> ArchiveConfig:
        """
        Reinitialize existing archive by clearing all tracked channels.

        Loads the existing archive and removes all channels from tracking.
        Does NOT delete any files - only clears the channel tracking list.

        Args:
            root_path: Path to existing archive

        Returns:
            Updated ArchiveConfig with empty channels dict
        """
        # Load existing config
        config = ConfigManager.load_archive(root_path)

        # Clear all channels
        config.channels = {}

        # Save updated config
        ConfigManager.save_archive(config)
        return config

    @staticmethod
    def load_archive(root_path: Path) -> ArchiveConfig:
        """
        Load existing archive config.

        Raises FileNotFoundError if archive not initialized.
        """
        config_path = ConfigManager.get_config_path(root_path)

        if not config_path.exists():
            raise FileNotFoundError(
                f"No archive found at {root_path}. "
                f"Run: subfetch init --root {root_path}"
            )

        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return ArchiveConfig.from_dict(data)

    @staticmethod
    def save_archive(config: ArchiveConfig):
        """Persist archive config to disk."""
        config_path = Path(config.root_path) / '.subfetch' / 'config.json'
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)

    @staticmethod
    def add_channel(
        config: ArchiveConfig,
        channel_id: str,
        channel_title: str,
        channel_url: str
    ) -> str:
        """
        Add channel to tracking list.

        Returns the folder name created for this channel.
        Raises ValueError if channel already tracked.
        """
        if channel_id in config.channels:
            existing = config.channels[channel_id]
            raise ValueError(
                f"Channel already tracked: {existing.channel_title} "
                f"(folder: {existing.folder_name})"
            )

        # Generate unique folder name
        root = Path(config.root_path)
        base_folder_name = sanitize_filename(channel_title, max_length=80)
        folder_name = ensure_unique_folder_name(root, base_folder_name)

        # Add to config
        channel_config = ChannelConfig(
            channel_id=channel_id,
            channel_title=channel_title,
            channel_url=channel_url,
            folder_name=folder_name,
            added_date=date.today().isoformat()
        )
        config.channels[channel_id] = channel_config

        # Create channel folder
        (root / folder_name).mkdir(parents=True, exist_ok=True)

        return folder_name

    @staticmethod
    def remove_channel(config: ArchiveConfig, channel_identifier: str) -> Optional[ChannelConfig]:
        """
        Remove channel by ID, handle, or folder name.

        Returns the removed ChannelConfig if found, None otherwise.
        """
        # Try direct channel ID lookup
        if channel_identifier in config.channels:
            return config.channels.pop(channel_identifier)

        # Try matching by folder name
        for channel_id, channel_config in list(config.channels.items()):
            if channel_config.folder_name == channel_identifier:
                return config.channels.pop(channel_id)

        # Try matching by channel title (case-insensitive)
        identifier_lower = channel_identifier.lower()
        for channel_id, channel_config in list(config.channels.items()):
            if channel_config.channel_title.lower() == identifier_lower:
                return config.channels.pop(channel_id)

        # Try matching by handle (remove @ if present)
        identifier_clean = channel_identifier.lstrip('@')
        for channel_id, channel_config in list(config.channels.items()):
            if identifier_clean in channel_config.channel_url:
                return config.channels.pop(channel_id)

        return None

    @staticmethod
    def find_channel(config: ArchiveConfig, channel_identifier: str) -> Optional[ChannelConfig]:
        """
        Find channel by ID, handle, folder name, or title.

        Returns ChannelConfig if found, None otherwise.
        """
        # Try direct channel ID lookup
        if channel_identifier in config.channels:
            return config.channels[channel_identifier]

        # Try matching by folder name
        for channel_config in config.channels.values():
            if channel_config.folder_name == channel_identifier:
                return channel_config

        # Try matching by channel title (case-insensitive)
        identifier_lower = channel_identifier.lower()
        for channel_config in config.channels.values():
            if channel_config.channel_title.lower() == identifier_lower:
                return channel_config

        # Try matching by handle (remove @ if present)
        identifier_clean = channel_identifier.lstrip('@')
        for channel_config in config.channels.values():
            if identifier_clean in channel_config.channel_url:
                return channel_config

        # Try matching handle against channel title with spaces/punctuation stripped
        # e.g. "@InspiringPhilosophy" matches title "Inspiring Philosophy"
        identifier_slug = re.sub(r'[\s\-_]', '', identifier_clean).lower()
        for channel_config in config.channels.values():
            title_slug = re.sub(r'[\s\-_]', '', channel_config.channel_title).lower()
            if identifier_slug == title_slug:
                return channel_config

        return None


class UserConfigManager:
    """Manages user-level global configuration (~/.subfetch_config)."""

    @staticmethod
    def get_user_config_path() -> Path:
        """Returns path to user config file in home directory."""
        return Path.home() / '.subfetch_config'

    @staticmethod
    def get_default_root() -> Optional[Path]:
        """Get the default archive root from user config."""
        config_path = UserConfigManager.get_user_config_path()

        if not config_path.exists():
            return None

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            root = data.get('default_root')
            if root:
                return Path(root)
        except (json.JSONDecodeError, OSError):
            pass

        return None

    @staticmethod
    def get_default_cookies() -> Optional[Path]:
        """Get the default cookies file from user config."""
        config_path = UserConfigManager.get_user_config_path()

        if not config_path.exists():
            return None

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            cookies = data.get('default_cookies')
            if cookies:
                return Path(cookies)
        except (json.JSONDecodeError, OSError):
            pass

        return None

    @staticmethod
    def set_default_root(root_path: Path):
        """Set the default archive root in user config."""
        config_path = UserConfigManager.get_user_config_path()

        # Load existing config to preserve other settings
        data = {}
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

        data['default_root'] = str(root_path.absolute())

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def set_default_cookies(cookies_path: Path):
        """Set the default cookies file in user config."""
        config_path = UserConfigManager.get_user_config_path()

        # Load existing config to preserve other settings
        data = {}
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

        data['default_cookies'] = str(cookies_path.absolute())

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def get_default_cookies_from_browser() -> Optional[str]:
        """Get the default browser name for cookies extraction from user config."""
        config_path = UserConfigManager.get_user_config_path()

        if not config_path.exists():
            return None

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('default_cookies_from_browser')
        except (json.JSONDecodeError, OSError):
            pass

        return None

    @staticmethod
    def set_default_cookies_from_browser(browser: str):
        """Set the default browser for cookies extraction in user config."""
        config_path = UserConfigManager.get_user_config_path()

        data = {}
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

        data['default_cookies_from_browser'] = browser

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def clear_default_root():
        """Clear the default archive root from user config."""
        config_path = UserConfigManager.get_user_config_path()

        if config_path.exists():
            config_path.unlink()


def resolve_root(root_arg: Optional[str]) -> Path:
    """
    Resolve the archive root path using priority order:
    1. Explicit --root argument (if provided)
    2. Current directory if it contains .subfetch/
    3. Default root from ~/.subfetch_config
    4. Raise error if none found

    Returns the resolved absolute Path.
    """
    # Priority 1: Explicit --root argument
    if root_arg and root_arg != '.':
        return Path(root_arg).expanduser().absolute()

    # Priority 2: Current directory if it contains .subfetch/
    cwd = Path.cwd()
    if (cwd / '.subfetch').exists():
        return cwd

    # Priority 3: Default root from user config
    default_root = UserConfigManager.get_default_root()
    if default_root:
        return default_root

    # Priority 4: Explicit '.' means current directory (even without .subfetch)
    if root_arg == '.':
        return cwd

    # No root found
    raise FileNotFoundError(
        "No archive found. Either:\n"
        "  1. Run from an archive directory (contains .subfetch/)\n"
        "  2. Set default root: subfetch init <path>\n"
        "  3. Specify --root: subfetch <command> --root <path>"
    )


def resolve_cookies(cookies_arg: Optional[str]) -> Optional[Path]:
    """
    Resolve the cookies file path using priority order:
    1. Explicit --cookies argument (if provided)
    2. Default cookies from ~/.subfetch_config
    3. Return None if not found

    Returns the resolved absolute Path or None.
    """
    # Priority 1: Explicit --cookies argument
    if cookies_arg:
        cookies_path = Path(cookies_arg).expanduser().absolute()
        if cookies_path.exists():
            return cookies_path
        return None

    # Priority 2: Default cookies from user config
    default_cookies = UserConfigManager.get_default_cookies()
    if default_cookies and default_cookies.exists():
        return default_cookies

    # No cookies found
    return None


def resolve_cookies_from_browser(browser_arg: Optional[str]) -> Optional[str]:
    """
    Resolve the browser name for cookies extraction using priority order:
    1. Explicit --browser argument (if provided)
    2. Default browser from ~/.subfetch_config
    3. Return None if not found

    Returns the browser name (e.g. 'chrome', 'firefox') or None.
    """
    if browser_arg:
        return browser_arg

    return UserConfigManager.get_default_cookies_from_browser()
