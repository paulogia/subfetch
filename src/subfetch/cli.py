"""CLI interface for subfetch."""

from pathlib import Path

import click

from . import __version__
from .channel import ChannelEnumerator
from .config import ConfigManager, UserConfigManager, resolve_root, resolve_cookies, resolve_cookies_from_browser
from .extractor import SubtitleExtractor
from .metadata import MetadataManager
from .sync import ChannelSynchronizer


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

        date_str = video.upload_date.isoformat() if video.upload_date else "????-??-??"
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
def add(channel: str, root: str):
    """Add channel to tracking list.

    CHANNEL can be a URL, @handle, or channel ID.

    Example: subfetch add "@3blue1brown"
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

    # Fetch channel info
    click.echo(f"Looking up channel: {channel}")
    enumerator = ChannelEnumerator()
    info = enumerator.get_channel_info(channel)

    if not info:
        click.echo(click.style(f"Error: Could not find channel: {channel}", fg='red'))
        raise SystemExit(1)

    # Add to config
    try:
        folder_name = ConfigManager.add_channel(
            config,
            info['channel_id'],
            info['channel_title'],
            info.get('channel_url', channel)
        )
        ConfigManager.save_archive(config)

        click.echo(click.style("Channel added!", fg='green'))
        click.echo(f"  Title: {info['channel_title']}")
        click.echo(f"  Channel ID: {info['channel_id']}")
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


@main.command('list')
@click.option('--root', type=click.Path(), default=None, help='Archive root directory')
def list_channels(root: str):
    """List monitored channels.

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
    click.echo(f"Tracked channels: {len(config.channels)}")
    click.echo()

    if not config.channels:
        click.echo("No channels tracked yet.")
        click.echo("Add channels with: subfetch add <channel>")
        return

    # Header
    click.echo(f"{'Channel':<30} {'ID':<26} {'Folder':<25} {'Videos':>8} {'Last Updated':<20}")
    click.echo("-" * 120)

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
        title = channel_config.channel_title[:28] + ".." if len(channel_config.channel_title) > 30 else channel_config.channel_title
        folder = channel_config.folder_name[:23] + ".." if len(channel_config.folder_name) > 25 else channel_config.folder_name

        click.echo(f"{title:<30} {channel_config.channel_id:<26} {folder:<25} {video_count:>8} {last_updated:<20}")


@main.command()
@click.option('--root', type=click.Path(), default=None, help='Archive root directory')
@click.option('--max-videos', '-n', type=int, help='Limit videos processed per channel')
@click.option('--max-total', type=int, help='Limit total videos processed across all channels (recommended: 400)')
@click.option('--channel', '-c', help='Process only specific channel (ID, @handle, or folder name)')
@click.option('--cookies', type=click.Path(exists=True), help='Path to cookies.txt file for authentication')
@click.option('--browser', type=click.Choice(['chrome', 'firefox', 'safari', 'edge', 'chromium']), default=None, help='Browser to extract cookies from (alternative to --cookies)')
@click.option('--delay', type=float, default=2.5, help='Seconds to wait between videos (default: 2.5, try 5-10 if rate limited)')
@click.option('--max-consecutive-failures', type=int, default=10, help='Stop after N consecutive missing captions (rate limit detection, default: 10)')
def run(root: str, max_videos: int, max_total: int, channel: str, cookies: str, browser: str, delay: float, max_consecutive_failures: int):
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
        title = video.title[:50] + "..." if len(video.title) > 50 else video.title

        if status == 'downloaded':
            symbol = click.style("✓", fg='green')
        elif status == 'skipped':
            symbol = click.style("⊘", fg='blue')
        elif status == 'missing_captions':
            symbol = click.style("✗", fg='yellow')
        else:  # error
            symbol = click.style("⚠", fg='red')

        date_str = video.upload_date.isoformat() if video.upload_date else "????-??-??"
        click.echo(f"{symbol} [{video.video_id}] {date_str} - {title}")

    # Run sync
    cookies_path = resolve_cookies(cookies)
    browser_source = resolve_cookies_from_browser(browser)
    synchronizer = ChannelSynchronizer(config, cookies_file=cookies_path, cookies_from_browser=browser_source)

    # Accumulate totals
    total_downloaded = 0
    total_skipped = 0
    total_missing = 0
    total_errors = 0
    total_processed = 0
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
            max_consecutive_failures=max_consecutive_failures
        )

        click.echo()
        if progress.rate_limited:
            click.echo(click.style(f"⚠ Rate limiting detected ({max_consecutive_failures} consecutive failures). Stopping channel sync.", fg='red', bold=True))
            click.echo(f"Channel progress: {progress.downloaded} downloaded, {progress.skipped} skipped, "
                       f"{progress.missing_captions} missing captions, {progress.errors} errors")
        else:
            click.echo(f"Channel complete: {progress.downloaded} downloaded, {progress.skipped} skipped, "
                       f"{progress.missing_captions} missing captions, {progress.errors} errors")

        # Accumulate totals
        total_downloaded += progress.downloaded
        total_skipped += progress.skipped
        total_missing += progress.missing_captions
        total_errors += progress.errors
        total_processed += progress.processed

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
        click.echo(f"  {click.style('⊘', fg='blue')} Skipped: {total_skipped}")
        click.echo(f"  {click.style('✗', fg='yellow')} Missing captions: {total_missing}")
        if total_errors > 0:
            click.echo(f"  {click.style('⚠', fg='red')} Errors: {total_errors}")
        if limit_reached:
            click.echo()
            click.echo("Run again to continue processing remaining videos.")
    elif limit_reached:
        click.echo()
        click.echo(click.style(f"⚠ Stopped after {total_processed} videos (limit: {max_total})", fg='yellow'))
        click.echo("Run again to continue processing.")


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


if __name__ == '__main__':
    main()
