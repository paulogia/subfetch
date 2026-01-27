# YouTube English Subtitle Extractor for Full Channels

## Version 1.0 --- Locked Specification

### Purpose

Build a tool that downloads and maintains a local archive of
**timestamped English transcripts** (from YouTube captions) for **entire
YouTube channels**, optimized for **searching and AI ingestion** rather
than subtitle playback. The tool must not download video media files.

------------------------------------------------------------------------

## 1. Scope

### Included Content

-   All public content types on a channel:
    -   Long-form videos
    -   Shorts
    -   Livestream archives / past streams

### Excluded Content

-   Video or audio media downloads
-   Private, unlisted, or members-only videos
-   Authentication/login handling
-   JSON transcript formats as primary output

------------------------------------------------------------------------

## 2. Core Functional Requirements

### 2.1 Channel Tracking

-   Maintain a persistent list of monitored channels.
-   Support commands to:
    -   Add a channel
    -   Remove a channel
    -   List monitored channels
-   Accepted input identifiers (v1):
    -   Channel URL
    -   @handle
    -   Channel ID
-   Internally normalize and store **Channel ID** as canonical
    identifier.

### 2.2 Storage Layout

-   User selects a master/root folder.
-   Create one subfolder per channel, named using the **channel display
    title** (human-readable).
-   Store channel metadata internally and preferably in a small metadata
    file inside the channel folder:
    -   Channel ID
    -   Channel title
    -   Channel URL / handle

### 2.3 Channel Enumeration

-   For each monitored channel, enumerate its full catalog of public
    videos, including:
    -   Shorts
    -   Livestream archives

### 2.4 Subtitle Selection Rules (English)

For each video, attempt captions in the following priority order:

1.  Uploaded English captions (any English variant: en, en-US, en-GB,
    en-CA, etc.)
2.  Auto-generated English captions
3.  English translated captions (acceptable fallback if no original
    English exists)

If no English captions are available: - Mark video as missing captions -
Retry on future runs (important for livestreams whose captions appear
later)

### 2.5 Incremental Sync & Self-Healing

-   Re-running the tool must:
    -   Download subtitles for new videos
    -   Download subtitles for previously missing-caption videos
    -   Avoid re-downloading subtitles that already exist
-   Detection should be existence-based using **video ID** to ensure
    self-healing behavior.
-   Tool must be safe to interrupt and resume.

------------------------------------------------------------------------

## 3. Output Requirements

### 3.1 File Format

-   Output format: `.srt` (v1)
-   Strict SRT compliance is **not required**
-   Format should remain minimal: timestamps + text

### 3.2 Provenance Metadata

Each subtitle file should begin with a short text header containing: -
Video title (at time of download) - Video URL - Video ID - Publish date
(if easily available)

Purpose: - Preserve traceability when files are concatenated - Enable
mapping AI search results back to original videos

### 3.3 File Naming

-   Filenames must be deterministic and collision-proof.
-   Must include **video ID**.
-   Suggested format:
    -   `YYYY-MM-DD - <sanitized title> [VIDEO_ID].srt`
-   If title or date unavailable, video ID alone must still guarantee
    uniqueness.

------------------------------------------------------------------------

## 4. Execution Model

### 4.1 Throttling & Stability

-   Use conservative request rates.
-   Avoid aggressive parallelism.
-   Prefer reliability over maximum throughput.

### 4.2 Resume & Retry Behavior

-   Failed or missing videos must be retried on later runs.
-   Tool must continue safely after interruptions.

### 4.3 Batch Limits

-   Support per-run caps on number of videos processed:
    -   Global cap or per-channel cap
-   Allows very large channels to be processed over multiple runs.

------------------------------------------------------------------------

## 5. Progress Feedback

-   Provide real-time progress output:
    -   Current channel
    -   Current video
    -   Status (downloaded / skipped / missing / failed)
-   Provide lightweight end-of-run summary:
    -   Total videos processed
    -   Downloaded
    -   Missing captions
    -   Failures

No heavy persistent log files required.

------------------------------------------------------------------------

## 6. Configuration & State

-   No external database.
-   All state stored locally in files under the master root.
-   Must persist:
    -   Master folder path
    -   Channel list (canonical channel IDs)
    -   Per-video processing status

Archive should be portable as a folder tree.

------------------------------------------------------------------------

## 7. Interface (v1 Recommendation)

Primary interface: **Command-line tool for macOS**

Example commands (illustrative):

-   `init --root <path>`
-   `add <channel>`
-   `remove <channel>`
-   `list`
-   `run [--max-videos N] [--channel <id>]`

CLI preferred for: - automation - Hazel integration - iterative
development

GUI/web interface explicitly not required for v1.

------------------------------------------------------------------------

## 8. Out of Scope for Version 1 (Planned Future Enhancements)

-   Post-processing `.srt` to `.txt` using user-supplied Hazel/bash
    script
-   Per-channel concatenated master transcript files
-   Auto-renaming channel folders if channel title changes
-   Caption refresh/re-download for already-downloaded videos (unless
    explicitly forced)

------------------------------------------------------------------------

## 9. Development Strategy

### Phase 0 --- Proof of Concept

1.  Download English subtitles for a single video.
2.  Enumerate all videos from a single channel.

### Phase 1 --- Minimal End-to-End

-   Add channel
-   Download subtitles for entire channel
-   Store to folders

### Phase 2 --- Incremental Updates

-   Resume behavior
-   Missing caption retries
-   Batch caps

### Phase 3 --- Performance & Stability

-   Throttling tuning
-   Improved retry logic

------------------------------------------------------------------------

## Design Philosophy

-   Conservative, polite network usage
-   Append-only archival model
-   Self-healing via file existence checks
-   Research-grade traceability
-   Optimized for long-term content analysis, not media playback
