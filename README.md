# subfetch - YouTube Subtitle Extractor

subfetch is a command-line tool that downloads and archives English subtitles from YouTube channels. It saves subtitles as text files that you can search through or feed to AI tools, without downloading any video or audio files.

## What does it do?

- Downloads English subtitles (captions) from YouTube videos
- Organizes subtitles by channel in folders
- Keeps track of which channels you want to monitor
- Automatically downloads subtitles from new videos when you run it again
- Works with regular videos, Shorts, and livestream archives

## Installation

### Step 1: Install Python
You need Python 3.9 or newer installed on your Mac. Check if you have it:

```bash
python3 --version
```

If you don't have Python, download it from [python.org](https://www.python.org/downloads/).

### Step 2: Install subfetch

First, make sure your pip is up to date:

```bash
python3 -m pip install --upgrade pip
```

Then install subfetch:

```bash
pip3 install -e /Users/pens/Documents/dev/subfetch
```

Or, if you're in the subfetch directory:

```bash
pip3 install -e .
```

**Note:** If you get an error about pip being too old or editable mode not working, you can install without the `-e` flag:
```bash
pip3 install /Users/pens/Documents/dev/subfetch
```

### Step 3: Fix PATH (if needed)

If you get a warning that subfetch is installed but "not on PATH", you need to add Python's bin directory to your PATH.

Add this line to your `~/.zshrc` file (or `~/.bash_profile` if using bash):
```bash
export PATH="$HOME/Library/Python/3.9/bin:$PATH"
```

Then restart Terminal or run:
```bash
source ~/.zshrc
```

**Alternative:** If you don't want to modify PATH, you can always use:
```bash
python3 -m subfetch
```
instead of just `subfetch` in all commands below.

### Step 4: Verify installation

Check that it's installed:

```bash
subfetch --version
```

Or:
```bash
python3 -m subfetch --version
```

## Quick Start Guide

Here's how to get started in 3 steps:

**Note:** If `subfetch` command isn't found, use `python3 -m subfetch` instead throughout these examples.

### 1. Create an archive folder

First, create a folder where all your subtitles will be stored:

```bash
subfetch init ~/youtube-subtitles
```

This creates a folder in your home directory called `youtube-subtitles` and tells subfetch to use it.

### 2. Add a YouTube channel or playlist

Add a channel or playlist you want to track. You can use the channel's @handle, URL, channel ID, playlist URL, or playlist ID:

```bash
# Add a channel
subfetch add "@3blue1brown"
```

Or with a full URL:

```bash
# Add a channel with URL
subfetch add "https://www.youtube.com/@veritasium"

# Add a playlist
subfetch add "https://www.youtube.com/playlist?list=PLxxx"
```

### 3. Download the subtitles

Now download all the subtitles from your tracked channels:

```bash
subfetch run
```

This will:
- Create a folder for each channel
- Download English subtitles for all videos
- Show progress as it works
- Skip videos that don't have English captions

That's it! Your subtitles are saved in `~/youtube-subtitles/`.

## All Available Commands

### `subfetch init <folder-path>`

Create a new archive folder and set it as your default location.

If the folder already exists as an archive, reinitializes it by clearing all tracked channels (with confirmation prompt). Individual transcript files are preserved.

**Example:**
```bash
subfetch init ~/youtube-subtitles
```

**What happens:**
- **New folder**: Creates archive structure and sets as default
- **Existing archive**: Prompts to confirm reinitialization, then clears all tracked channels (files are NOT deleted)

**Options:**
- `--no-set-default` - Don't set this as the default archive (useful if you want multiple archives)

**Use cases for reinitializing:**
- Start fresh with a new set of channels to track
- Clear out channels you no longer want to monitor
- Reset tracking state while keeping existing transcript files

---

### `subfetch config-cookies <cookies-file>`

Set a default cookies file to use for all operations (useful for age-restricted or members-only videos).

**Example:**
```bash
subfetch config-cookies ~/youtube-cookies.txt
```

**What it does:**
- Saves the cookies file path in `~/.subfetch_config`
- All commands will automatically use this cookies file
- You can still override with `--cookies` for individual commands

**How to get a cookies file:**
1. Install a browser extension like "Get cookies.txt LOCALLY" (Chrome) or "cookies.txt" (Firefox)
2. Go to youtube.com while logged in
3. Export cookies to a file
4. Set it as default with this command

---

### `subfetch add <channel-or-playlist>`

Add a YouTube channel or playlist to your tracking list.

**Examples:**
```bash
# Add a channel
subfetch add "@3blue1brown"
subfetch add "https://www.youtube.com/@veritasium"
subfetch add "UCHnyfMqiRRG1u-2MsSQLbXA"

# Add a playlist
subfetch add "https://www.youtube.com/playlist?list=PLxxx"
subfetch add "PLxxx"

# Add a skeptical channel or playlist (compilation links go to separate folder)
subfetch add "@skepticchannel" --skeptical
subfetch add "PLxxx" --skeptical

# Include live stream replay subtitles for this channel
subfetch add "@livestreamer" --lives
```

**Options:**
- `--root <path>` - Use a different archive folder (if you have multiple)
- `--skeptical` - Mark this source as skeptical (compilation links go to `_compilations_skeptical/` instead of `_compilations/`)
- `--lives` - Enable downloading subtitles for live stream replays (stored in a separate `ChannelName-live-NNN.txt` cumulative file)

**Categories:**
Both channels and playlists can be marked as "main" (default, for Christian content) or "skeptical". This organizes compilation hard links into separate folders for easier management.

**Supported formats:**
- **Channels**: @handle, channel URL, channel ID
- **Playlists**: playlist URL, playlist ID (starts with PL, RD, UU, FL, LP, or LL)

---

### `subfetch mark-skeptical <channel>`

Mark an existing channel as skeptical.

Compilation hard links for this channel will be moved to the skeptical folder when you next run `subfetch update-links`.

**Example:**
```bash
subfetch mark-skeptical "@channel"
subfetch update-links --clean  # Reorganize links
```

**Options:**
- `--root <path>` - Use a different archive folder

---

### `subfetch unmark-skeptical <channel>`

Remove skeptical marking from a channel (mark it as main).

Compilation hard links for this channel will be moved back to the main folder when you next run `subfetch update-links`.

**Example:**
```bash
subfetch unmark-skeptical "@channel"
subfetch update-links --clean  # Reorganize links
```

**Options:**
- `--root <path>` - Use a different archive folder

---

### `subfetch mark-lives <channel>`

Enable live stream subtitle downloading for an existing channel.

When enabled, live stream replays are downloaded and stored in a separate `ChannelName-live-NNN.txt` cumulative file (so they don't mix with regular video transcripts). Live streams are also exempt from no-subtitle strikes for a grace period after airing.

**Example:**
```bash
subfetch mark-lives "@livestreamer"
```

**Options:**
- `--root <path>` - Use a different archive folder

---

### `subfetch unmark-lives <channel>`

Disable live stream subtitle downloading for a channel.

**Example:**
```bash
subfetch unmark-lives "@livestreamer"
```

**Options:**
- `--root <path>` - Use a different archive folder

---

### `subfetch list`

Show all channels and playlists you're tracking and how many subtitles you've downloaded.

**Example:**
```bash
subfetch list
```

**Options:**
- `--root <path>` - Use a different archive folder

**Output shows:**
- Type (Channel or Playlist)
- Title
- ID
- Folder name
- Category (main or skeptical)
- Number of subtitle files downloaded
- Last time it was updated

---

### `subfetch remove <channel>`

Stop tracking a channel (doesn't delete the subtitle files unless you tell it to).

**Examples:**
```bash
subfetch remove "@3blue1brown"
subfetch remove "3Blue1Brown"
```

**Options:**
- `--delete-folder` - Also delete all the subtitle files for this channel
- `--root <path>` - Use a different archive folder

---

### `subfetch run`

Download subtitles for all your tracked channels. This is the main command you'll use regularly.

**Basic usage:**
```bash
subfetch run
```

**Options:**
- `--max-videos <number>` or `-n <number>` - Limit how many videos to process per channel
- `--channel <channel>` or `-c <channel>` - Only sync one specific channel
- `--root <path>` - Use a different archive folder
- `--cookies <path>` - Use a cookies file for age-restricted or members-only content
- `--update-links` - Update compilation hard links after sync completes

**Examples:**
```bash
# Download from all channels
subfetch run

# Only process 50 videos from each channel
subfetch run --max-videos 50

# Stop after 400 videos total (prevents rate limiting)
subfetch run --max-total 400

# Only sync one specific channel
subfetch run --channel "@veritasium"

# Combine options for rate-limited large channels
subfetch run --max-total 400 --delay 5.0
```

**What happens:**
- subfetch checks each channel for new videos
- Downloads English subtitles for videos you don't have yet
- Skips videos you've already downloaded
- Shows progress with symbols:
  - ✓ (green) = Downloaded successfully
  - ⊘ (blue) = Already have it, skipped
  - ✗ (yellow) = No English captions available
  - ⚠ (red) = Error occurred

---

### `subfetch update-links`

Create a master folder with hard links to all cumulative compilation files.

This command creates a `_compilations/` folder in your archive root that contains hard links to all `ChannelName-NNN.txt` cumulative files across all channels. This makes it easy to:
- Access all compilation files in one place
- Sort by date modified in Finder to see recently updated channels
- Quickly identify which channels have new content since your last manual copy

**Note:** Hard links share the exact same modification time as the original files (they're literally the same file with two names). When you sort by "Date Modified" in the `_compilations/` folder, you'll see which channels have been updated most recently.

**Basic usage:**
```bash
subfetch update-links
```

**Options:**
- `--clean` - Remove all existing links and rebuild from scratch
- `--root <path>` - Use a different archive folder

**Examples:**
```bash
# Update hard links (safe to run multiple times)
subfetch update-links

# Clean rebuild (remove all and recreate)
subfetch update-links --clean

# Update links for specific archive
subfetch update-links --root ~/work-research
```

**What happens:**
- Creates `_compilations/` folder if it doesn't exist
- Creates hard links to all `ChannelName-NNN.txt` files
- Removes stale links (for deleted channels/files)
- Skips creating links that already exist and are valid
- Shows summary of created/removed links

---

### `subfetch config-auto-links [on|off]`

Enable or disable automatic hard link updates after each sync.

When enabled, `subfetch run` will automatically update the compilation hard links at the end of each sync, so you don't have to manually run `subfetch update-links`.

**Examples:**
```bash
# Enable automatic updates
subfetch config-auto-links on

# Disable automatic updates
subfetch config-auto-links off
```

**Options:**
- `--root <path>` - Use a different archive folder

**What happens:**
- Saves the preference in your archive config
- When enabled: `subfetch run` automatically updates hard links at the end
- When disabled: You must manually run `subfetch update-links` to update links

**Use case:**
- Enable if you want hard links always up-to-date without extra commands
- Disable if you prefer manual control or don't use the links feature

---

### `subfetch video <video-url>`

Download subtitles for just one video (without tracking the whole channel).

**Example:**
```bash
subfetch video "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

**Options:**
- `--output <folder>` or `-o <folder>` - Where to save the subtitle file
- `--cookies <path>` - Use a cookies file for age-restricted videos

---

### `subfetch list-videos <channel>`

See all the videos in a channel without downloading anything (useful for previewing).

**Example:**
```bash
subfetch list-videos "@3blue1brown"
```

**Options:**
- `--limit <number>` or `-n <number>` - Only show the first N videos

## Common Workflows

### Daily/weekly archiving routine

```bash
# Just run this command regularly:
subfetch run
```

It will only download new videos, so it's safe to run as often as you want.

### Start with a limited download

If a channel has thousands of videos, start with a small batch:

```bash
subfetch add "@channelname"
subfetch run --channel "@channelname" --max-videos 100
```

Then later, run it again to get more:

```bash
subfetch run --channel "@channelname" --max-videos 100
```

### Manage multiple archives

You can have different archive folders for different purposes:

```bash
# Create archives
subfetch init ~/work-research --no-set-default
subfetch init ~/personal-learning --no-set-default

# Add channels to specific archives
subfetch add "@computerphile" --root ~/work-research
subfetch add "@3blue1brown" --root ~/personal-learning

# Sync specific archives
subfetch run --root ~/work-research
```

## Where are my files?

Subtitles are organized like this:

```
~/youtube-subtitles/
├── .subfetch_config.json          (tracking info - don't edit)
├── _compilations/                 (hard links for main channels/playlists - optional)
│   ├── 3Blue1Brown-001.txt        (hard link, same modification date as original)
│   ├── 3Blue1Brown-002.txt
│   ├── Veritasium-001.txt
│   ├── My Favorite Videos-001.txt (playlist)
│   └── ...
├── _compilations_skeptical/       (hard links for skeptical sources - optional)
│   ├── SkepticalChannel-001.txt
│   ├── Skeptical Playlist-001.txt
│   └── ...
├── 3Blue1Brown/                   (channel folder)
│   ├── .channel_metadata.json     (channel info)
│   ├── 3Blue1Brown-001.txt        (cumulative file)
│   ├── 2024-01-15 - Linear algebra [abc123].txt
│   ├── 2024-02-20 - Calculus [def456].txt
│   └── ...
├── Veritasium/                    (channel folder)
│   ├── .channel_metadata.json
│   ├── Veritasium-001.txt          (cumulative file)
│   ├── 2024-01-10 - Physics explained [ghi789].txt
│   └── ...
├── My Favorite Videos/            (playlist folder)
│   ├── .channel_metadata.json
│   ├── My Favorite Videos-001.txt (cumulative file)
│   ├── 2024-03-01 - Video from various channels [xyz123].txt
│   └── ...
└── SkepticalChannel/
    ├── .channel_metadata.json
    ├── SkepticalChannel-001.txt    (cumulative file)
    └── ...
```

**Note:** The `_compilations/` and `_compilations_skeptical/` folders are only created if you run `subfetch update-links` or enable auto-update with `subfetch config-auto-links on`. Files in these folders are hard links (not copies) - they share the same modification date as the originals, making it easy to sort by "Date Modified" to see recently updated channels. Channels are automatically organized by category: main (Christian) channels go to `_compilations/`, while skeptical channels go to `_compilations_skeptical/`.

Each subtitle file:
- Has the video ID in brackets at the end (so it's always unique)
- Includes the upload date
- Contains a header with video info (title, URL, date)
- Is in simplified SRT format (timestamp-prefixed text, not full SRT)

The format looks like this:
```
# Video: Example Video Title
# URL: https://youtube.com/watch?v=abc123
# Video ID: abc123
# Publish Date: 2024-01-15
# Subtitle Type: auto-generated
# Downloaded: 2024-01-20

00:00:01 Hello and welcome to this video
00:00:05 Today we're going to talk about
00:00:08 something really interesting
```

This simplified format is optimized for searching and AI ingestion rather than video playback.

### Cumulative Files

In addition to individual transcript files, subfetch automatically creates **cumulative files** that combine all transcripts from a channel into larger aggregated files. This makes it easier to search across all videos or feed entire channel transcripts to AI tools.

**How cumulative files work:**

- **Incremental appending**: Each video is appended to the cumulative file immediately after download (not at the end of sync)
- **Interruption-safe**: If sync is interrupted, all downloaded videos up to that point are already in the cumulative file
- **File naming**: `{ChannelName}-{number}.txt` (e.g., `3Blue1Brown-001.txt`, `3Blue1Brown-002.txt`)
- **Size limit**: Each cumulative file is capped at 10MB. When this limit is reached, a new numbered file is created
- **Content**: Full transcript content including provenance headers and timestamps
- **Separator**: Videos are separated by a line of 80 equals signs (`====...====`)

**Example cumulative file content:**
```
# Video: First Video Title
# URL: https://youtube.com/watch?v=abc123
# Video ID: abc123
# Publish Date: 2024-01-15
# Subtitle Type: auto-generated
# Downloaded: 2024-01-26

00:00:01 Hello and welcome
00:00:05 This is the first video
================================================================================
# Video: Second Video Title
# URL: https://youtube.com/watch?v=def456
# Video ID: def456
# Publish Date: 2024-01-20
# Subtitle Type: auto-generated
# Downloaded: 2024-01-26

00:00:01 Welcome to video two
00:00:08 More content here
```

**When to use cumulative files:**
- Searching across all videos in a channel at once
- Feeding entire channel transcripts to AI/LLM tools
- Quick browsing without opening many individual files
- Creating channel-wide analysis or summaries

**Note**: Individual transcript files remain the source of truth. Cumulative files are automatically regenerated as you download new videos.

### Playlists

subfetch supports tracking YouTube playlists just like channels. This is useful for curated collections of videos from various creators or for tracking specific series within a channel.

**Adding playlists:**

```bash
# Add a public playlist
subfetch add "https://www.youtube.com/playlist?list=PLxxx"

# Add with just the playlist ID
subfetch add "PLxxx"

# Mark as skeptical
subfetch add "PLxxx" --skeptical
```

**How playlists work:**

- **Same as channels**: Playlists are tracked, synced, and organized exactly like channels
- **Separate folders**: Each playlist gets its own folder named after the playlist title
- **Compilation files**: Playlists create cumulative files and hard links just like channels
- **Category support**: Playlists can be marked as "main" or "skeptical" like channels
- **Auto-sync**: Running `subfetch run` syncs all tracked playlists and channels

**Supported playlist types:**

- **Public playlists**: Work without authentication
- **Unlisted playlists**: Work if you have the URL
- **Private playlists**: Require authentication (use `--cookies` or `--browser`)

**Use cases for playlists:**

- Track a curated collection of apologetics videos from various channels
- Monitor a specific series within a channel (e.g., a debate series)
- Archive educational playlists without tracking entire channels
- Organize content by topic rather than by creator

**Differences from channels:**

- Playlist videos come from various channels, but all download to one playlist folder
- Playlist ownership is tracked (shows creator's channel name in `subfetch add` output)
- Playlists may change over time as the owner adds/removes videos

**Example workflow:**

```bash
# Add a playlist
subfetch add "https://www.youtube.com/playlist?list=PLxxx"

# View all tracked sources (shows both channels and playlists)
subfetch list

# Sync everything (playlists and channels)
subfetch run

# Mark a playlist as skeptical
subfetch mark-skeptical "Playlist Name"
```

## Tips for Non-Technical Users

### How to open Terminal
1. Press `Command + Space` to open Spotlight
2. Type "Terminal" and press Enter

### How to find your home folder
In Terminal, `~` means your home folder. To see the full path:
```bash
echo ~
```

### If a command isn't working
- Make sure you're typing it exactly as shown
- Channel names with @symbols should be in quotes: `"@channelname"`
- URLs should be in quotes: `"https://..."`

### How to stop a running command
If `subfetch run` is taking too long, press `Control + C` to stop it. You can safely run it again later - it will pick up where it left off.

## Troubleshooting

### "Command not found: pip"
This is the most common issue on Mac. Use `pip3` instead:
```bash
pip3 install -e /Users/pens/Documents/dev/subfetch
```

Or use this alternative:
```bash
python3 -m pip install -e /Users/pens/Documents/dev/subfetch
```

### "editable mode currently requires a setup.py" or pip version too old
If you get an error about pip being too old (e.g., "version 25.3 is available"), upgrade pip first:
```bash
python3 -m pip install --upgrade pip
```

Then try installing again. Or, skip the upgrade and install without editable mode:
```bash
pip3 install /Users/pens/Documents/dev/subfetch
```

### "Command not found: subfetch"
If subfetch was working before but stopped after restarting your computer, your virtual environment may not be activated. From the subfetch directory, run:

```bash
source .venv/bin/activate
```

You'll need to do this each time you open a new terminal session.

If that's not the issue, this can also happen when Python's bin directory isn't in your PATH.

**Quick solution:** Use `python3 -m subfetch` instead of `subfetch` for all commands.

**Permanent solution:** Add Python's bin to your PATH:
```bash
echo 'export PATH="$HOME/Library/Python/3.9/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

Then `subfetch` will work directly.

### "No module named 'subfetch'"
- You need to install it first: `pip3 install -e /Users/pens/Documents/dev/subfetch`

### "Channel not found"
- Check that you're using the correct @handle or URL
- Try the full channel URL instead of just the @handle

### "No English captions available"
- Some videos don't have English subtitles
- For livestreams, captions might appear hours or days after the stream ends
- Run `subfetch run` again later to catch videos that get captions added

### Videos show captions on YouTube but not in subfetch

This issue has multiple causes:

**1. Rate Limiting (Most Common for Large Channels)**

When processing hundreds or thousands of videos, YouTube may start blocking subtitle metadata requests. You'll see many videos marked as "missing captions" even though they have them.

**Symptoms:**
- First ~200-500 videos download fine, then most fail
- Debug mode shows `Available subtitles: []` and `Available automatic: []`
- Same videos work when tested individually

**Solutions:**
- **Set a total video limit** (prevents hitting rate limits):
  ```bash
  # Stop after 400 videos total
  subfetch run --max-total 400
  # Run again after 30-60 minutes to continue
  subfetch run --max-total 400
  # Repeat until all videos processed
  ```

- **Use cookies** (helps bypass rate limits):
  ```bash
  subfetch config-cookies ~/youtube-cookies.txt
  subfetch run --channel "@channelname"
  ```

- **Increase delay between videos**:
  ```bash
  subfetch run --channel "@channelname" --delay 5.0
  # or even longer for very aggressive rate limiting
  subfetch run --channel "@channelname" --delay 10.0
  ```

- **Combine strategies** (most effective):
  ```bash
  # Use cookies + limit + delay
  subfetch run --max-total 400 --delay 5.0 --cookies ~/youtube-cookies.txt
  ```

**2. Authentication Required**

Some videos require authentication to access captions via the API, even if they're publicly viewable in a browser:
- Age-restricted videos (18+)
- Members-only content
- Some videos where YouTube blocks API access

**Solution:** Use a cookies file (see above)

### Debug Mode

If videos are being marked as "missing captions" but you believe they should have English captions, enable debug mode to see detailed error information:

```bash
export SUBFETCH_DEBUG=1
subfetch run --channel "@channelname" --max-videos 5
```

This will show:
- Which step is failing (video info extraction, subtitle detection, or download)
- Available subtitle languages for each video
- Detailed error messages from yt-dlp

To disable debug mode:
```bash
unset SUBFETCH_DEBUG
```

**Common issues revealed by debug mode:**
- Rate limiting from YouTube (wait 30-60 minutes and try again)
- Network timeouts (retry later or reduce `--max-videos`)
- Missing cookies for restricted content (use `--cookies`)

### Automatic Rate Limiting Detection

subfetch automatically detects when YouTube is rate limiting you and stops early to avoid wasting your quota:

**How it works:**
- After 10 consecutive "missing captions" (all with empty subtitle lists), subfetch assumes you're rate limited and stops
- You'll see: `⚠ Rate limiting detected (10 consecutive failures). Stopping channel sync.`
- This prevents burning through your `--max-total` budget on failed requests

**To adjust sensitivity:**
```bash
# More aggressive (stop after 5 failures)
subfetch run --max-consecutive-failures 5

# Less aggressive (stop after 20 failures)
subfetch run --max-consecutive-failures 20
```

**What to do when rate limited:**
1. Wait 30-60 minutes (or longer for severe limiting)
2. Try using cookies: `subfetch config-cookies ~/youtube-cookies.txt`
3. Use longer delays: `subfetch run --delay 5.0`
4. For channels with 1000+ videos, you may need to wait 12-24 hours after hitting rate limits

## Future Updates

When new features are added to subfetch, this README will be updated to reflect them. Check the [changelog or version history] for what's new in each version.

## Current Version

Version: 0.2.1

## Questions or Issues?

If something isn't working, check:
1. You've run `subfetch init` to create an archive
2. You've added at least one channel with `subfetch add`
3. You have internet connection
4. The channel exists and is public
