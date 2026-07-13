"""CLI interface for subfetch."""

from pathlib import Path

import click

from . import __version__
from .channel import ChannelEnumerator
from .config import ConfigManager, UserConfigManager, resolve_root, resolve_cookies, resolve_cookies_from_browser
from .extractor import SubtitleExtractor
from .metadata import MetadataManager
from .sync import ChannelSynchronizer
from .symlinks import SymlinkManager


@click.group()
@click.version_option(version=__version__)
def main():
    """subfetch - YouTube subtitle extractor for channel archiving."""
    pass


@main.command()
@click.argument('video_url')
@click.option(
    '--output', '-o',
    type=click.Path(),
    default='.',
    help='Output directory for subtitle file'
)
@click.option(
    '--cookies',
    type=click.Path(exists=True),
    help='Path to cookies.txt file for authentication'
)
@click.option(
    '--browser',
    type=click.Choice(['chrome', 'firefox', 'safari', 'edge', 'chromium']),
    default=None,
    help='Browser to extract cookies from (alternative to --cookies)'
)
def video(video_url: str, output: str, cookies: str, browser: str):
    """Download subtitles for a single video.

    Example: subfetch video "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    """
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)

    cookies_path = resolve_cookies(cookies)
    browser_source = resolve_cookies_from_browser(browser)
    extractor = SubtitleExtractor(output_path, cookies_file=cookies_path, cookies_from_browser=browser_source)

    click.echo(f"Extracting subtitles from: {video_url}")
    result = extractor.extract(video_url)

    if result.success:
        click.echo(click.style("Success!", fg='green'))
        click.echo(f"  Title: {result.video.title}")
        click.echo(f"  Type: {result.subtitle_type.value}")
        click.echo(f"  Saved: {result.file_path}")
    else:
        click.echo(click.style(f"Failed: {result.error}", fg='red'))
        raise SystemExit(1)


@main.command('list-videos')
@click.argument('channel')
@click.option(
    '--limit', '-n',
    type=int,
    default=None,
    help='Limit number of videos to list'
)
def list_videos(channel: str, limit: int):
    """List all videos from a channel.

    CHANNEL can be a URL, @handle, or channel ID.

    Example: subfetch list-videos "@3blue1brown"
    """
    enumerator = ChannelEnumerator()

    click.echo(f"Enumerating videos from: {channel}")

    # Get channel info first
    info = enumerator.get_channel_info(channel)
    if info:
        click.echo(f"Channel: {info['channel_title']}")
        click.echo(f"Channel ID: {info['channel_id']}")
        click.echo("-" * 50)

    count = 0
    for video in enumerator.enumerate(channel):
        if limit and count >= limit:
            click.echo(f"... (limited to {limit} videos)")
            break

        date_str = video.upload_date.isoformat() if video.upload_date else "????"
        # Truncate title for display
        title = video.title[:60] + "..." if len(video.title) > 60 else video.title
        click.echo(f"[{video.video_id}] {date_str} - {title}")
        count += 1

    click.echo("-" * 50)
    click.echo(f"Total: {count} videos")


@main.command()
@click.argument('root_path', type=click.Path())
@click.option('--set-default/--no-set-default', default=True,
              help='Set this as the default archive root')
def init(root_path: str, set_default: bool):
    """Initialize archive root directory.

    If archive already exists, reinitializes it (clears all tracked channels).

    Example: subfetch init ~/youtube-archive
    """
    root = Path(root_path).expanduser().absolute()

    try:
        config = ConfigManager.init_archive(root)

        # Set as default root
        if set_default:
            UserConfigManager.set_default_root(root)
            click.echo(click.style("Archive initialized and set as default!", fg='green'))
        else:
            click.echo(click.style("Archive initialized!", fg='green'))

        click.echo(f"  Location: {config.root_path}")

        if set_default:
            click.echo(f"  Default: Yes (stored in ~/.subfetch_config)")

        click.echo()
        click.echo("Next steps:")
        click.echo(f"  1. Add channels: subfetch add <channel>")
        click.echo(f"  2. Download subtitles: subfetch run")
    except FileExistsError:
        # Archive already exists - prompt to reinitialize
        try:
            existing_config = ConfigManager.load_archive(root)
            num_channels = len(existing_config.channels)

            if num_channels > 0:
                click.echo(click.style(f"Archive already exists at {root}", fg='yellow'))
                click.echo(f"Currently tracking {num_channels} channel(s):")
                for channel in existing_config.channels.values():
                    click.echo(f"  - {channel.channel_title}")
                click.echo()
                click.echo(click.style("WARNING: Reinitializing will remove all tracked channels.", fg='red', bold=True))
                click.echo("(Individual transcript files will NOT be deleted)")
                click.echo()

                if not click.confirm("Do you want to reinitialize this archive?"):
                    click.echo("Cancelled.")
                    raise SystemExit(0)

            # Reinitialize (clear channels)
            config = ConfigManager.reinit_archive(root)

            if set_default:
                UserConfigManager.set_default_root(root)
                click.echo(click.style("Archive reinitialized and set as default!", fg='green'))
            else:
                click.echo(click.style("Archive reinitialized!", fg='green'))

            click.echo(f"  Location: {config.root_path}")
            click.echo(f"  Channels: 0 (cleared)")

            if set_default:
                click.echo(f"  Default: Yes (stored in ~/.subfetch_config)")

            click.echo()
            click.echo("Next steps:")
            click.echo(f"  1. Add channels: subfetch add <channel>")
            click.echo(f"  2. Download subtitles: subfetch run")

        except Exception as e:
            click.echo(click.style(f"Error: {e}", fg='red'))
            raise SystemExit(1)


@main.command('config-cookies')
@click.argument('cookies_file', type=click.Path(exists=True))
def config_cookies(cookies_file: str):
    """Set default cookies file for authentication.

    Example: subfetch config-cookies ~/youtube-cookies.txt
    """
    cookies_path = Path(cookies_file).expanduser().absolute()

    if not cookies_path.exists():
        click.echo(click.style(f"Error: Cookies file not found: {cookies_path}", fg='red'))
        raise SystemExit(1)

    UserConfigManager.set_default_cookies(cookies_path)
    click.echo(click.style("Default cookies file configured!", fg='green'))
    click.echo(f"  Location: {cookies_path}")
    click.echo(f"  Stored in: ~/.subfetch_config")
    click.echo()
    click.echo("This cookies file will now be used automatically for all operations.")
    click.echo("You can override it with --cookies for individual commands.")


@main.command('config-cookies-browser')
@click.argument('browser', type=click.Choice(['chrome', 'firefox', 'safari', 'edge', 'chromium']))
def config_cookies_browser(browser: str):
    """Set default browser to extract cookies from automatically.

    Reads cookies directly from the browser's profile, which often works
    better than an exported cookies.txt for YouTube PO token authentication.

    Examples:

      subfetch config-cookies-browser chrome

      subfetch config-cookies-browser firefox
    """
    UserConfigManager.set_default_cookies_from_browser(browser)
    click.echo(click.style("Default browser for cookies configured!", fg='green'))
    click.echo(f"  Browser: {browser}")
    click.echo(f"  Stored in: ~/.subfetch_config")
    click.echo()
    click.echo("Cookies will now be read from this browser for all operations.")
    click.echo("You can override it with --browser for individual commands.")


@main.command()
@click.argument('channel')
@click.option('--root', type=click.Path(), default=None, help='Archive root directory')
@click.option('--skeptical', is_flag=True, help='Mark this channel as skeptical')
@click.option('--lives', is_flag=True, help='Enable live stream subtitle downloading for this channel')
def add(channel: str, root: str, skeptical: bool, lives: bool):
    """Add channel or playlist to tracking list.

    CHANNEL can be a channel URL, @handle, channel ID, playlist URL, or playlist ID.

    Examples:
      subfetch add "@3blue1brown"
      subfetch add "https://www.youtube.com/playlist?list=PLxxx"
      subfetch add "PLxxx" --skeptical
      subfetch add "@livestreamer" --lives
    """
    try:
        root_path = resolve_root(root)
    except FileNotFoundError as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        raise SystemExit(1)

    try:
        config = ConfigManager.load_archive(root_path)
    except FileNotFoundError as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        raise SystemExit(1)

    # Fetch channel/playlist info
    source_label = "playlist" if ('list=' in channel or channel.startswith(('PL', 'RD', 'UU', 'FL', 'LP', 'LL'))) else "channel"
    click.echo(f"Looking up {source_label}: {channel}")
    enumerator = ChannelEnumerator()
    info = enumerator.get_channel_info(channel)

    if not info:
        click.echo(click.style(f"Error: Could not find {source_label}: {channel}", fg='red'))
        raise SystemExit(1)

    # Add to config
    try:
        folder_name = ConfigManager.add_channel(
            config,
            info['channel_id'],
            info['channel_title'],
            info.get('channel_url', channel)
        )

        # Set category and flags based on options
        channel_config = config.channels[info['channel_id']]
        channel_config.category = "skeptical" if skeptical else "main"
        channel_config.include_lives = lives

        # Set source type and owner info for playlists
        if info.get('source_type') == 'playlist':
            channel_config.source_type = 'playlist'
            channel_config.owner_channel_id = info.get('owner_channel_id')
            channel_config.owner_channel_name = info.get('owner_channel_name')

        ConfigManager.save_archive(config)

        category_label = click.style("skeptical", fg='yellow') if skeptical else click.style("main", fg='cyan')
        source_label = "Playlist" if info.get('source_type') == 'playlist' else "Channel"
        click.echo(click.style(f"{source_label} added!", fg='green'))
        click.echo(f"  Title: {info['channel_title']}")
        click.echo(f"  ID: {info['channel_id']}")
        if info.get('source_type') == 'playlist' and info.get('owner_channel_name'):
            click.echo(f"  Owner: {info['owner_channel_name']}")
        click.echo(f"  Category: {category_label}")
        click.echo(f"  Lives: {click.style('enabled', fg='green') if lives else 'disabled'}")
        click.echo(f"  Folder: {root_path / folder_name}")
        click.echo(f"  Videos: {info.get('video_count', '?')}")
        click.echo()
        click.echo("Run 'subfetch run' to download subtitles.")

    except ValueError as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        raise SystemExit(1)


@main.command()
@click.argument('channel')
@click.option('--root', type=click.Path(), default=None, help='Archive root directory')
@click.option('--delete-folder', is_flag=True, help='Also delete channel folder')
def remove(channel: str, root: str, delete_folder: bool):
    """Remove channel from tracking.

    CHANNEL can be ID, @handle, folder name, or channel title.

    Example: subfetch remove "@3blue1brown"
    """
    try:
        root_path = resolve_root(root)
    except FileNotFoundError as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        raise SystemExit(1)

    try:
        config = ConfigManager.load_archive(root_path)
    except FileNotFoundError as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        raise SystemExit(1)

    # Remove channel
    removed = ConfigManager.remove_channel(config, channel)

    if removed is None:
        click.echo(click.style(f"Error: Channel not found: {channel}", fg='red'))
        raise SystemExit(1)

    ConfigManager.save_archive(config)

    click.echo(click.style("Channel removed from tracking!", fg='green'))
    click.echo(f"  Title: {removed.channel_title}")
    click.echo(f"  Channel ID: {removed.channel_id}")

    folder_path = root_path / removed.folder_name
    if folder_path.exists():
        # Count files
        srt_count = len(list(folder_path.glob('*.srt')))
        click.echo(f"  Folder: {folder_path} ({srt_count} subtitle files)")

        if delete_folder:
            import shutil
            shutil.rmtree(folder_path)
            click.echo(click.style("  Folder deleted.", fg='yellow'))
        else:
            click.echo("  Folder preserved. Use --delete-folder to remove it.")


@main.command('mark-skeptical')
@click.option('--root', type=click.Path(), default=None, help='Archive root directory')
@click.argument('channel')
def mark_skeptical(root: str, channel: str):
    """Mark a channel as skeptical.

    Compilation links for this channel will be placed in the skeptical folder.

    CHANNEL can be ID, @handle, folder name, or channel title.

    Example: subfetch mark-skeptical "@skepticchannel"
    """
    try:
        root_path = resolve_root(root)
    except FileNotFoundError as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        raise SystemExit(1)

    try:
        config = ConfigManager.load_archive(root_path)
    except FileNotFoundError as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        raise SystemExit(1)

    # Find channel
    channel_config = ConfigManager.find_channel(config, channel)

    if channel_config is None:
        click.echo(click.style(f"Error: Channel not found: {channel}", fg='red'))
        raise SystemExit(1)

    # Set category
    channel_config.category = "skeptical"
    ConfigManager.save_archive(config)

    click.echo(click.style("Channel marked as skeptical!", fg='green'))
    click.echo(f"  Title: {channel_config.channel_title}")
    click.echo(f"  Category: {click.style('skeptical', fg='yellow')}")
    click.echo()
    click.echo("Run 'subfetch update-links --clean' to reorganize compilation links.")


@main.command('unmark-skeptical')
@click.option('--root', type=click.Path(), default=None, help='Archive root directory')
@click.argument('channel')
def unmark_skeptical(root: str, channel: str):
    """Mark a channel as main (remove skeptical marking).

    Compilation links for this channel will be placed in the main folder.

    CHANNEL can be ID, @handle, folder name, or channel title.

    Example: subfetch unmark-skeptical "@channel"
    """
    try:
        root_path = resolve_root(root)
    except FileNotFoundError as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        raise SystemExit(1)

    try:
        config = ConfigManager.load_archive(root_path)
    except FileNotFoundError as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        raise SystemExit(1)

    # Find channel
    channel_config = ConfigManager.find_channel(config, channel)

    if channel_config is None:
        click.echo(click.style(f"Error: Channel not found: {channel}", fg='red'))
        raise SystemExit(1)

    # Set category
    channel_config.category = "main"
    ConfigManager.save_archive(config)

    click.echo(click.style("Channel marked as main!", fg='green'))
    click.echo(f"  Title: {channel_config.channel_title}")
    click.echo(f"  Category: {click.style('main', fg='cyan')}")
    click.echo()
    click.echo("Run 'subfetch update-links --clean' to reorganize compilation links.")


@main.command('mark-lives')
@click.option('--root', type=click.Path(), default=None, help='Archive root directory')
@click.argument('channel')
def mark_lives(root: str, channel: str):
    """Enable live stream subtitle downloading for a channel.

    When enabled, live stream replays are downloaded into a separate
    ChannelName-live-NNN.txt compilation file, and fresh live streams
    are exempt from no-subtitle strikes.

    CHANNEL can be ID, @handle, folder name, or channel title.

    Example: subfetch mark-lives "@livestreamer"
    """
    try:
        root_path = resolve_root(root)
    except FileNotFoundError as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        raise SystemExit(1)

    try:
        config = ConfigManager.load_archive(root_path)
    except FileNotFoundError as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        raise SystemExit(1)

    channel_config = ConfigManager.find_channel(config, channel)

    if channel_config is None:
        click.echo(click.style(f"Error: Channel not found: {channel}", fg='red'))
        raise SystemExit(1)

    channel_config.include_lives = True
    ConfigManager.save_archive(config)

    click.echo(click.style("Live stream downloading enabled!", fg='green'))
    click.echo(f"  Title: {channel_config.channel_title}")
    click.echo(f"  Lives: {click.style('enabled', fg='green')}")
    click.echo()
    click.echo("Run 'subfetch run' to download live stream subtitles.")


@main.command('unmark-lives')
@click.option('--root', type=click.Path(), default=None, help='Archive root directory')
@click.argument('channel')
def unmark_lives(root: str, channel: str):
    """Disable live stream subtitle downloading for a channel.

    CHANNEL can be ID, @handle, folder name, or channel title.

    Example: subfetch unmark-lives "@livestreamer"
    """
    try:
        root_path = resolve_root(root)
    except FileNotFoundError as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        raise SystemExit(1)

    try:
        config = ConfigManager.load_archive(root_path)
    except FileNotFoundError as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        raise SystemExit(1)

    channel_config = ConfigManager.find_channel(config, channel)

    if channel_config is None:
        click.echo(click.style(f"Error: Channel not found: {channel}", fg='red'))
        raise SystemExit(1)

    channel_config.include_lives = False
    ConfigManager.save_archive(config)

    click.echo(click.style("Live stream downloading disabled!", fg='green'))
    click.echo(f"  Title: {channel_config.channel_title}")
    click.echo(f"  Lives: disabled")


@main.command('list')
@click.option('--root', type=click.Path(), default=None, help='Archive root directory')
def list_channels(root: str):
    """List monitored channels and playlists.

    Example: subfetch list
    """
    try:
        root_path = resolve_root(root)
    except FileNotFoundError as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        raise SystemExit(1)

    try:
        config = ConfigManager.load_archive(root_path)
    except FileNotFoundError as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        raise SystemExit(1)

    click.echo(f"Archive: {config.root_path}")
    click.echo(f"Tracked sources: {len(config.channels)}")
    click.echo()

    if not config.channels:
        click.echo("No channels or playlists tracked yet.")
        click.echo("Add sources with: subfetch add <channel or playlist>")
        return

    # Header
    click.echo(f"{'Type':<10} {'Title':<25} {'ID':<26} {'Folder':<20} {'Category':<12} {'Lives':<7} {'Videos':>8} {'Last Updated':<20}")
    click.echo("-" * 145)

    for channel_config in config.channels.values():
        folder_path = root_path / channel_config.folder_name

        # Count subtitle files
        video_count = 0
        last_updated = "(never synced)"

        if folder_path.exists():
            video_count = len(list(folder_path.glob('*.srt')))

            # Try to get last updated from metadata
            metadata = MetadataManager.load(folder_path)
            if metadata:
                last_updated = metadata.last_updated[:10]  # Just the date part

        # Truncate long names
        title = channel_config.channel_title[:23] + ".." if len(channel_config.channel_title) > 25 else channel_config.channel_title
        folder = channel_config.folder_name[:18] + ".." if len(channel_config.folder_name) > 20 else channel_config.folder_name

        # Get source type with color coding
        source_type = getattr(channel_config, 'source_type', 'channel')
        if source_type == 'playlist':
            type_display = click.style("Playlist", fg='magenta')
        else:
            type_display = click.style("Channel", fg='blue')

        # Get category with color coding
        category = getattr(channel_config, 'category', 'main')  # Default to 'main' for backward compat
        if category == "skeptical":
            category_display = click.style("skeptical", fg='yellow')
        else:
            category_display = click.style("main", fg='cyan')

        # Show lives flag
        include_lives = getattr(channel_config, 'include_lives', False)
        lives_display = click.style("yes", fg='green') if include_lives else "-"

        click.echo(f"{type_display:<18} {title:<25} {channel_config.channel_id:<26} {folder:<20} {category_display:<20} {lives_display:<7} {video_count:>8} {last_updated:<20}")


@main.command()
@click.option('--root', type=click.Path(), default=None, help='Archive root directory')
@click.option('--max-videos', '-n', type=int, help='Limit videos processed per channel')
@click.option('--max-total', type=int, help='Limit total videos processed across all channels (recommended: 400)')
@click.option('--channel', '-c', help='Process only specific channel (ID, @handle, or folder name)')
@click.option('--cookies', type=click.Path(exists=True), help='Path to cookies.txt file for authentication')
@click.option('--browser', type=click.Choice(['chrome', 'firefox', 'safari', 'edge', 'chromium']), default=None, help='Browser to extract cookies from (alternative to --cookies)')
@click.option('--delay', type=float, default=2.5, help='Seconds to wait between videos (default: 2.5, try 5-10 if rate limited)')
@click.option('--max-consecutive-failures', type=int, default=10, help='Stop after N consecutive missing captions or errors (rate limit detection, default: 10)')
@click.option('--no-sub-threshold', type=int, default=2, help='Skip video permanently after N confirmed no-subtitle results (default: 2)')
@click.option('--live-grace-days', type=int, default=7, help='Days a live stream video is exempt from no-subtitle strikes (default: 7)')
@click.option('--update-links', is_flag=True, help='Update compilation symlinks after sync completes')
def run(root: str, max_videos: int, max_total: int, channel: str, cookies: str, browser: str, delay: float, max_consecutive_failures: int, no_sub_threshold: int, live_grace_days: int, update_links: bool):
    """Download subtitles for all tracked channels.

    Examples:
      subfetch run                    # Sync all channels
      subfetch run --max-videos 100   # Limit to 100 videos per channel
      subfetch run --max-total 400    # Stop after 400 videos total (prevents rate limiting)
      subfetch run --channel @3blue1brown  # Sync only one channel
      subfetch run --delay 5.0        # Increase delay to avoid rate limits
    """
    try:
        root_path = resolve_root(root)
    except FileNotFoundError as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        raise SystemExit(1)

    try:
        config = ConfigManager.load_archive(root_path)
    except FileNotFoundError as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        raise SystemExit(1)

    if not config.channels:
        click.echo("No channels to sync.")
        click.echo("Add channels with: subfetch add <channel>")
        return

    # Filter to specific channel if requested
    channels_to_sync = list(config.channels.values())
    if channel:
        found = ConfigManager.find_channel(config, channel)
        if found:
            channels_to_sync = [found]
        else:
            click.echo(click.style(f"Error: Channel not found: {channel}", fg='red'))
            raise SystemExit(1)

    # Progress callback for real-time updates
    def progress_callback(channel_title: str, video, status: str):
        # Truncate title for display
        raw_title = video.title or video.video_id
        title = raw_title[:50] + "..." if len(raw_title) > 50 else raw_title

        if status in ('skipped', 'skipped_no_subtitles', 'skipped_errored'):
            return
        elif status == 'downloaded':
            symbol = click.style("✓", fg='green')
        elif status == 'missing_captions':
            symbol = click.style("✗", fg='yellow')
        else:  # error
            symbol = click.style("⚠", fg='red')

        date_str = video.upload_date.isoformat() if video.upload_date else "????"
        click.echo(f"{symbol} [{video.video_id}] {date_str} - {title}")

    # Run sync
    cookies_path = resolve_cookies(cookies)
    browser_source = resolve_cookies_from_browser(browser)
    synchronizer = ChannelSynchronizer(config, cookies_file=cookies_path, cookies_from_browser=browser_source)

    # Accumulate totals
    total_downloaded = 0
    total_skipped = 0
    total_skipped_no_subtitles = 0
    total_skipped_errored = 0
    total_missing = 0
    total_errors = 0
    total_processed = 0
    total_channel_videos_sum = 0
    limit_reached = False

    for idx, channel_config in enumerate(channels_to_sync, 1):
        # Check if we've hit the global limit
        if max_total and total_processed >= max_total:
            limit_reached = True
            click.echo()
            click.echo(click.style(f"⚠ Reached total video limit ({max_total}). Stopping.", fg='yellow', bold=True))
            click.echo(f"Processed {idx - 1} of {len(channels_to_sync)} channels.")
            break

        click.echo()
        click.echo(click.style(f"Syncing: {channel_config.channel_title} [{idx}/{len(channels_to_sync)}]", fg='cyan', bold=True))
        click.echo("-" * 80)

        # Calculate remaining budget for this channel
        remaining = None
        if max_total:
            remaining = max_total - total_processed
            # Use the smaller of max_videos or remaining budget
            if max_videos:
                effective_max = min(max_videos, remaining)
            else:
                effective_max = remaining
        else:
            effective_max = max_videos

        progress = synchronizer.sync_channel(
            channel_config.channel_id,
            max_videos=effective_max,
            progress_callback=progress_callback,
            delay=delay,
            max_consecutive_failures=max_consecutive_failures,
            no_sub_threshold=no_sub_threshold,
            live_grace_days=live_grace_days,
        )

        click.echo()
        def _channel_summary_line(p) -> str:
            parts = [
                f"{p.downloaded} downloaded",
                f"{p.skipped} skipped",
            ]
            if p.skipped_no_subtitles:
                parts.append(f"{p.skipped_no_subtitles} no-subtitles")
            if p.skipped_errored:
                parts.append(f"{p.skipped_errored} errored")
            parts += [f"{p.missing_captions} missing captions", f"{p.errors} errors"]
            return ", ".join(parts)

        if progress.rate_limited:
            click.echo(click.style(f"⚠ Stopped after {max_consecutive_failures} consecutive failures (rate limiting or errors). Stopping channel sync.", fg='red', bold=True))
            click.echo(f"Channel progress: {_channel_summary_line(progress)}")
        else:
            click.echo(f"Channel complete: {_channel_summary_line(progress)}")

        # Completeness indicator
        ch_has = progress.downloaded + progress.skipped
        ch_total = progress.total_channel_videos or progress.processed
        ch_not_seen = ch_total - progress.processed
        ch_pending = progress.missing_captions + progress.errors
        ch_addressable = ch_total - progress.skipped_no_subtitles - progress.skipped_errored
        if ch_addressable > 0:
            ch_pct = ch_has / ch_addressable * 100
            pct_str = click.style(f"{ch_pct:.0f}%", fg='green' if ch_pct >= 95 else 'yellow')
            parts = [f"{ch_has}/{ch_addressable} addressable videos have subtitles ({pct_str})"]
            if ch_not_seen > 0:
                parts.append(f"{ch_not_seen} not yet seen")
            if ch_pending > 0:
                parts.append(f"{ch_pending} pending retry")
            click.echo(f"  → {', '.join(parts)}")

        # Accumulate totals
        total_downloaded += progress.downloaded
        total_skipped += progress.skipped
        total_skipped_no_subtitles += progress.skipped_no_subtitles
        total_skipped_errored += progress.skipped_errored
        total_missing += progress.missing_captions
        total_errors += progress.errors
        total_processed += progress.processed
        total_channel_videos_sum += progress.total_channel_videos or progress.processed

        # If rate limited, stop processing other channels too
        if progress.rate_limited:
            click.echo()
            click.echo(click.style("⚠ YouTube is rate limiting subtitle requests.", fg='yellow', bold=True))
            click.echo("Wait 30-60 minutes (or longer) before trying again.")
            click.echo("Consider using --cookies and --delay options.")
            limit_reached = True  # Reuse this flag to show stopped message
            break

    # Final summary
    if len(channels_to_sync) > 1:
        click.echo()
        if limit_reached:
            click.echo(click.style("=== Sync Stopped (Limit Reached) ===", fg='yellow', bold=True))
        else:
            click.echo(click.style("=== Sync Complete ===", fg='green', bold=True))
        click.echo(f"Channels: {len(channels_to_sync)}")
        click.echo(f"Videos processed: {total_processed}")
        if max_total:
            click.echo(f"  (limit: {max_total})")
        click.echo(f"  {click.style('✓', fg='green')} Downloaded: {total_downloaded}")
        click.echo(f"  {click.style('⊘', fg='blue')} Skipped (already downloaded): {total_skipped}")
        if total_skipped_no_subtitles > 0:
            click.echo(f"  {click.style('⊘', fg='bright_black')} Skipped (no subtitles): {total_skipped_no_subtitles}")
        if total_skipped_errored > 0:
            click.echo(f"  {click.style('⊘', fg='bright_black')} Skipped (errored): {total_skipped_errored}")
        click.echo(f"  {click.style('✗', fg='yellow')} Missing captions: {total_missing}")
        if total_errors > 0:
            click.echo(f"  {click.style('⚠', fg='red')} Errors: {total_errors}")
        total_has = total_downloaded + total_skipped
        total_addressable = total_processed - total_skipped_no_subtitles - total_skipped_errored
        total_pending = total_missing + total_errors
        if total_addressable > 0:
            total_pct = total_has / total_addressable * 100
            pct_color = 'green' if total_pct >= 95 else 'yellow'
            click.echo(f"Subtitle coverage: {total_has}/{total_addressable} ({click.style(f'{total_pct:.1f}%', fg=pct_color)})")
        if total_pending > 0:
            click.echo(f"Pending retry next run: {total_pending}")
        # Track not-yet-seen across channels
        if total_channel_videos_sum > total_processed:
            click.echo(f"Not yet seen: {total_channel_videos_sum - total_processed}")
        if limit_reached:
            click.echo()
            click.echo("Run again to continue processing remaining videos.")
    elif limit_reached:
        click.echo()
        click.echo(click.style(f"⚠ Stopped after {total_processed} videos (limit: {max_total})", fg='yellow'))
        click.echo("Run again to continue processing.")

    # Update hard links if requested or enabled in config
    if update_links or config.auto_update_links:
        click.echo()
        click.echo(click.style("Updating compilation links...", fg='cyan'))
        created, removed, errors = SymlinkManager.update_links(config, verbose=False)

        if created > 0 or removed > 0:
            click.echo(f"  {click.style('✓', fg='green')} Created: {created} hard links")
            if removed > 0:
                click.echo(f"  {click.style('⊘', fg='blue')} Removed: {removed} stale links")
            if errors > 0:
                click.echo(f"  {click.style('⚠', fg='yellow')} Errors: {errors}")
        else:
            click.echo(f"  {click.style('✓', fg='green')} All links up to date")


@main.command('rebuild-transcripts')
@click.option('--root', type=click.Path(), default=None, help='Archive root directory')
@click.option('--channel', '-c', help='Rebuild only specific channel (ID, @handle, or folder name)')
def rebuild_transcripts(root: str, channel: str):
    """Rebuild cumulative transcript files from individual subtitle files.

    Deletes all existing channel-NNN.txt files and recreates them from the
    individual per-video subtitle files, using the current size limit.

    Useful after changing the size limit, or to fix any inconsistencies.

    Examples:
      subfetch rebuild-transcripts
      subfetch rebuild-transcripts --channel @3blue1brown
    """
    from .cumulative import CumulativeManager

    try:
        root_path = resolve_root(root)
    except FileNotFoundError as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        raise SystemExit(1)

    try:
        config = ConfigManager.load_archive(root_path)
    except FileNotFoundError as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        raise SystemExit(1)

    channels_to_rebuild = list(config.channels.values())
    if channel:
        found = ConfigManager.find_channel(config, channel)
        if found:
            channels_to_rebuild = [found]
        else:
            click.echo(click.style(f"Error: Channel not found: {channel}", fg='red'))
            raise SystemExit(1)

    limit_mb = CumulativeManager.MAX_SIZE_BYTES // (1024 * 1024)
    click.echo(f"Rebuilding cumulative transcripts (limit: {limit_mb}MB per file)")
    click.echo()

    total_files = 0
    for channel_config in channels_to_rebuild:
        folder_path = root_path / channel_config.folder_name
        if not folder_path.exists():
            click.echo(f"  {channel_config.channel_title}: folder not found, skipping")
            continue

        click.echo(f"  {channel_config.channel_title}...", nl=False)
        count = CumulativeManager.rebuild_channel(folder_path, channel_config.channel_title)
        total_files += count
        click.echo(click.style(f" {count} files", fg='green'))

    click.echo()
    click.echo(click.style("Done.", fg='green'))
    click.echo(f"Processed {total_files} subtitle files across {len(channels_to_rebuild)} channel(s).")


@main.command('inspect-video')
@click.argument('video')
@click.option(
    '--cookies',
    type=click.Path(exists=True),
    help='Path to cookies.txt file for authentication'
)
@click.option(
    '--browser',
    type=click.Choice(['chrome', 'firefox', 'safari', 'edge', 'chromium']),
    default=None,
    help='Browser to extract cookies from (alternative to --cookies)'
)
@click.option(
    '--json', 'output_json', is_flag=True, default=False,
    help='Output raw JSON of subtitle info'
)
def inspect_video(video: str, cookies: str, browser: str, output_json: bool):
    """Inspect subtitle metadata for a single video without downloading.

    VIDEO can be a full YouTube URL or a bare video ID.

    Prints exactly what yt-dlp sees for subtitles and what subfetch
    would select, bypassing all download logic. Useful for diagnosing
    why a video is reported as missing captions.

    Examples:

      subfetch inspect-video 4t4nL4E5074

      subfetch inspect-video "https://www.youtube.com/watch?v=4t4nL4E5074"

      subfetch inspect-video 4t4nL4E5074 --json
    """
    import json as json_mod

    import yt_dlp

    url = video if video.startswith('http') else f'https://www.youtube.com/watch?v={video}'

    cookies_path = resolve_cookies(cookies)
    browser_source = resolve_cookies_from_browser(browser)

    # Use download=False with the ios player client. The ios player API JSON is
    # fetched during info extraction regardless of download mode, and it includes
    # full caption track data — so automatic_captions will be populated without
    # needing to go through format selection (which fails due to PO token).
    ydl_opts: dict = {
        'quiet': False,         # show yt-dlp progress/warnings for diagnosis
        'no_warnings': False,
        'ignoreerrors': True,
        'extractor_args': {
            'youtube': {'player_client': ['ios']},
        },
    }
    if cookies_path and cookies_path.exists():
        ydl_opts['cookiefile'] = str(cookies_path)
    elif browser_source:
        ydl_opts['cookiesfrombrowser'] = (browser_source,)

    click.echo(f"Fetching metadata for: {url}")
    click.echo()

    info = None
    try:
        # process=False: return raw info dict without running process_ie_result,
        # which would trigger format selection and fail (all ios formats need PO token).
        # The ios player API JSON is still fetched in _real_extract, so
        # automatic_captions is populated with subtitle URLs.
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False, process=False)
    except Exception as e:
        click.echo(click.style(f"Warning: yt-dlp raised an exception ({e})", fg='yellow'))

    if info is None:
        click.echo(click.style("yt-dlp returned no info for this video.", fg='red'))
        raise SystemExit(1)

    subtitles = info.get('subtitles', {})
    automatic_captions = info.get('automatic_captions', {})

    if output_json:
        click.echo(json_mod.dumps({
            'id': info.get('id'),
            'title': info.get('title'),
            'subtitles': {k: [{'ext': t.get('ext')} for t in v] if isinstance(v, list) else v
                         for k, v in subtitles.items()},
            'automatic_captions': {k: [{'ext': t.get('ext')} for t in v] if isinstance(v, list) else v
                                   for k, v in automatic_captions.items()},
        }, indent=2))
        return

    click.echo()
    click.echo(click.style(f"Video ID : {info.get('id', 'unknown')}", bold=True))
    click.echo(click.style(f"Title    : {info.get('title', 'unknown')}", bold=True))
    click.echo()

    def _show_tracks(label: str, color: str, track_dict: dict) -> None:
        if track_dict:
            click.echo(click.style(f"{label}:", fg=color, bold=True))
            for lang_key, tracks in track_dict.items():
                fmts = [t.get('ext', '?') for t in tracks] if isinstance(tracks, list) else []
                click.echo(f"  {lang_key!r:24s} {fmts}")
        else:
            click.echo(click.style(f"{label}: (none)", fg='yellow'))

    _show_tracks("Uploaded subtitles", 'green', subtitles)
    click.echo()
    _show_tracks("Automatic captions", 'cyan', automatic_captions)
    click.echo()

    from .extractor import SubtitleExtractor
    from .models import SubtitleType

    subtitles_info = {'subtitles': subtitles, 'automatic_captions': automatic_captions}
    extractor = SubtitleExtractor.__new__(SubtitleExtractor)
    sub_type, lang_code, is_auto = extractor._select_best_subtitle(subtitles_info)

    if sub_type is not None:
        click.echo(click.style(
            f"subfetch would select: type={sub_type.value!r}, lang={lang_code!r}, is_auto={is_auto}",
            fg='green', bold=True
        ))
    else:
        click.echo(click.style("subfetch would report: No English subtitles available", fg='red', bold=True))
        en_subs = [k for k in subtitles if k.lower().startswith('en')]
        en_auto = [k for k in automatic_captions if k.lower().startswith('en')]
        if en_subs or en_auto:
            click.echo(click.style("NOTE: 'en*' keys present but not matched:", fg='yellow'))
            if en_subs:
                click.echo(f"  subtitles: {en_subs}")
            if en_auto:
                click.echo(f"  automatic_captions: {en_auto}")


@main.command('update-links')
@click.option('--root', type=click.Path(), default=None, help='Archive root directory')
@click.option('--clean', is_flag=True, help='Remove all links and recreate from scratch')
def update_links(root: str, clean: bool):
    """Update hard links to cumulative compilation files.

    Creates a master folder (_compilations/) with hard links to all channel
    compilation files. Safe to run multiple times - only creates/updates
    what's needed.

    Hard links share the same modification date as the original files,
    making it easy to identify recently updated channels by sorting by
    "Date Modified" in Finder.

    Examples:
      subfetch update-links
      subfetch update-links --clean
    """
    try:
        root_path = resolve_root(root)
    except FileNotFoundError as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        raise SystemExit(1)

    try:
        config = ConfigManager.load_archive(root_path)
    except FileNotFoundError as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        raise SystemExit(1)

    if not config.channels:
        click.echo("No channels tracked yet.")
        click.echo("Add channels with: subfetch add <channel>")
        return

    click.echo(click.style("Updating compilation links...", fg='cyan'))

    created, removed, errors = SymlinkManager.update_links(config, clean=clean, verbose=True)

    click.echo()
    if clean:
        click.echo(click.style("Clean rebuild complete!", fg='green'))
    else:
        click.echo(click.style("Update complete!", fg='green'))

    click.echo(f"  Created: {created} hard links")
    if removed > 0:
        click.echo(f"  Removed: {removed} stale links")
    if errors > 0:
        click.echo(f"  Errors: {errors}")

    compilations_folder_main = SymlinkManager.get_compilations_folder(config, "main")
    compilations_folder_skeptical = SymlinkManager.get_compilations_folder(config, "skeptical")
    click.echo()
    click.echo(f"Main links: {compilations_folder_main}")
    click.echo(f"Skeptical links: {compilations_folder_skeptical}")


@main.command('config-auto-links')
@click.option('--root', type=click.Path(), default=None, help='Archive root directory')
@click.argument('enabled', type=click.Choice(['on', 'off']))
def config_auto_links(root: str, enabled: str):
    """Enable or disable automatic link updates after sync.

    When enabled, 'subfetch run' will automatically update compilation
    hard links after completing the sync.

    Examples:
      subfetch config-auto-links on
      subfetch config-auto-links off
    """
    try:
        root_path = resolve_root(root)
    except FileNotFoundError as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        raise SystemExit(1)

    try:
        config = ConfigManager.load_archive(root_path)
    except FileNotFoundError as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        raise SystemExit(1)

    config.auto_update_links = (enabled == 'on')
    ConfigManager.save_archive(config)

    if config.auto_update_links:
        click.echo(click.style("✓ Auto-update enabled!", fg='green'))
        click.echo("Hard links will be updated automatically after 'subfetch run'")
    else:
        click.echo(click.style("✓ Auto-update disabled", fg='blue'))
        click.echo("Use 'subfetch update-links' to manually update links")


if __name__ == '__main__':
    main()
