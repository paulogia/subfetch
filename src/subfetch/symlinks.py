"""Hard link management for cumulative compilation files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple, Set

from .config import ArchiveConfig
from .utils import sanitize_filename


class SymlinkManager:
    """Manages hard links to cumulative compilation files."""

    @staticmethod
    def update_links(
        config: ArchiveConfig,
        clean: bool = False,
        verbose: bool = True
    ) -> Tuple[int, int, int]:
        """
        Update hard links in compilations folders for all categories.

        Scans all channel folders for cumulative files and creates/updates
        hard links in the appropriate compilations folder based on category.
        Removes stale hard links.

        Args:
            config: Archive configuration
            clean: If True, remove all links and rebuild from scratch
            verbose: If True, print progress messages

        Returns:
            (created_count, removed_count, error_count) tuple
        """
        total_created = 0
        total_removed = 0
        total_errors = 0

        # Update links for main category
        created, removed, errors = SymlinkManager._update_links_for_category(
            config, "main", clean, verbose
        )
        total_created += created
        total_removed += removed
        total_errors += errors

        # Update links for skeptical category
        created, removed, errors = SymlinkManager._update_links_for_category(
            config, "skeptical", clean, verbose
        )
        total_created += created
        total_removed += removed
        total_errors += errors

        return total_created, total_removed, total_errors

    @staticmethod
    def _update_links_for_category(
        config: ArchiveConfig,
        category: str,
        clean: bool = False,
        verbose: bool = True
    ) -> Tuple[int, int, int]:
        """
        Update hard links for channels of a specific category.

        Args:
            config: Archive configuration
            category: "main" or "skeptical"
            clean: If True, remove all links and rebuild from scratch
            verbose: If True, print progress messages

        Returns:
            (created_count, removed_count, error_count) tuple
        """
        compilations_folder = SymlinkManager.get_compilations_folder(config, category)

        # Create compilations folder if it doesn't exist
        compilations_folder.mkdir(parents=True, exist_ok=True)

        created = 0
        removed = 0
        errors = 0

        # Clean mode: remove all existing files
        if clean:
            removed = SymlinkManager.remove_all_links(compilations_folder)

        # Find all cumulative files for this category
        cumulative_files = SymlinkManager.find_all_cumulatives(
            Path(config.root_path),
            config,
            category=category
        )

        # Build set of expected filenames
        expected_names = {f.name for f in cumulative_files}

        # Create hard links for each cumulative file
        for cumulative_path in cumulative_files:
            link_path = compilations_folder / cumulative_path.name

            # Skip if valid hard link already exists (same file)
            if link_path.exists():
                try:
                    if link_path.samefile(cumulative_path):
                        continue  # Already linked correctly
                    else:
                        # File exists but is not the same - remove it
                        link_path.unlink()
                except OSError:
                    # If samefile fails, try to remove and recreate
                    try:
                        link_path.unlink()
                    except OSError:
                        pass

            # Create hard link
            if SymlinkManager.create_hardlink_safe(cumulative_path, link_path, verbose):
                created += 1
            else:
                errors += 1

        # Remove stale links (files that don't match current cumulatives)
        removed += SymlinkManager.remove_stale_links(
            compilations_folder,
            expected_names,
            verbose
        )

        return created, removed, errors

    @staticmethod
    def find_all_cumulatives(
        root_path: Path,
        config: ArchiveConfig,
        category: str = None
    ) -> List[Path]:
        """
        Scan all channel folders for cumulative compilation files.

        Args:
            root_path: Archive root path
            config: Archive configuration
            category: Optional category filter ("main" or "skeptical"). If None, returns all.

        Returns:
            List of absolute paths to cumulative files (*-NNN.txt)
        """
        cumulative_files = []

        for channel_config in config.channels.values():
            # Filter by category if specified
            if category is not None:
                channel_category = getattr(channel_config, 'category', 'main')
                if channel_category != category:
                    continue

            channel_folder = root_path / channel_config.folder_name

            if not channel_folder.exists():
                continue

            safe_title = sanitize_filename(channel_config.channel_title, max_length=80)

            # Find regular cumulative files: ChannelName-NNN.txt (anchored match)
            for file in channel_folder.glob(f"{safe_title}-*.txt"):
                if re.match(rf'^{re.escape(safe_title)}-(\d{{3}})\.txt$', file.name):
                    cumulative_files.append(file.absolute())

            # Find live cumulative files: ChannelName-live-NNN.txt
            safe_live_title = f"{safe_title}-live"
            for file in channel_folder.glob(f"{safe_live_title}-*.txt"):
                if re.match(rf'^{re.escape(safe_live_title)}-(\d{{3}})\.txt$', file.name):
                    cumulative_files.append(file.absolute())

        return cumulative_files

    @staticmethod
    def create_hardlink_safe(
        target: Path,
        link: Path,
        verbose: bool = True
    ) -> bool:
        """
        Create hard link with error handling.

        Args:
            target: Absolute path to target file
            link: Path where hard link will be created
            verbose: If True, print warnings on errors

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create hard link
            link.hardlink_to(target)
            return True

        except FileExistsError:
            if verbose:
                print(f"Warning: {link.name} already exists")
            return False
        except OSError as e:
            if verbose:
                print(f"Warning: Failed to create hard link {link.name}: {e}")
            return False

    @staticmethod
    def remove_stale_links(
        folder: Path,
        expected_names: Set[str],
        verbose: bool = True
    ) -> int:
        """
        Remove files in folder that don't match expected cumulative files.

        Args:
            folder: Path to scan for stale files
            expected_names: Set of expected filenames
            verbose: If True, print warnings

        Returns:
            Count of removed files
        """
        removed_count = 0

        if not folder.exists():
            return 0

        for item in folder.iterdir():
            # Skip directories and hidden files
            if item.is_dir() or item.name.startswith('.'):
                continue

            # Check if this file matches a current cumulative pattern
            if item.name not in expected_names:
                # Check if it looks like a cumulative file pattern
                if re.search(r'-\d{3}\.txt$', item.name):
                    if verbose:
                        print(f"Removing stale link: {item.name}")
                    try:
                        item.unlink()
                        removed_count += 1
                    except OSError as e:
                        if verbose:
                            print(f"Warning: Failed to remove {item.name}: {e}")

        return removed_count

    @staticmethod
    def remove_all_links(folder: Path) -> int:
        """
        Remove all files in folder (for clean rebuild).

        Args:
            folder: Path to scan for files

        Returns:
            Count of removed files
        """
        removed_count = 0

        if not folder.exists():
            return 0

        for item in folder.iterdir():
            # Only remove .txt files matching cumulative pattern, skip hidden files
            if item.is_file() and not item.name.startswith('.') and re.search(r'-\d{3}\.txt$', item.name):
                try:
                    item.unlink()
                    removed_count += 1
                except OSError:
                    pass

        return removed_count

    @staticmethod
    def get_compilations_folder(config: ArchiveConfig, category: str = "main") -> Path:
        """
        Get absolute path to compilations folder for a specific category.

        Args:
            config: Archive configuration
            category: "main" or "skeptical" (default: "main")

        Returns:
            Path to compilations folder
        """
        root = Path(config.root_path)
        if category == "skeptical":
            folder_name = getattr(config, 'compilations_folder_skeptical', '_compilations_skeptical')
        else:
            folder_name = getattr(config, 'compilations_folder', '_compilations')
        return root / folder_name
