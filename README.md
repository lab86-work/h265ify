# h265ify

GPU-only HEVC/H.265 video transcoder. Detects available hardware encoders (NVENC, QSV, VAAPI, MediaCodec) and batch-re-encodes video files in-place.

## How it works

1. **Hardware detection** — queries `ffmpeg -encoders` for available GPU HEVC encoders.
2. **File scanning** — walks a folder (optionally recursive) for video files (`mp4`, `mkv`, `avi`, `mov`, etc.).
3. **Codec check** — uses `ffprobe` to skip files already in H.265/HEVC.
4. **Transcode** — re-encodes the video stream with the detected GPU encoder, re-muxes audio with configurable codec/bitrate.
5. **Atomic output** — writes to a `.processing` temp file, then renames to final (e.g. `video_JP.mkv`). Original is either deleted or renamed to `.to_delete` for manual review.

Supports Spanish audio detection (`-map 0:m:language:spa`) via `EXTRA_ARGS` in `.env`.

## Requirements

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/) with GPU HEVC encoder support
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

```bash
# Clone
git clone <repo-url> && cd h265ify

# Set up env
cp .env.sample .env

# Install with uv
make install

# Or with pip
uv sync
```

## Usage

```bash
# Transcode all videos in a folder
h265ify /path/to/videos

# Recursive — process subfolders
h265ify /path/to/videos -r

# Dry run — preview without transcoding
h265ify /path/to/videos --dry-run

# Force a specific encoder
h265ify /path/to/videos --encoder hevc_nvenc

# Delete originals after successful transcode
h265ify /path/to/videos --delete
```

## Configuration

Copy `.env.sample` to `.env` and edit:

| Variable | Default | Description |
|---|---|---|
| `AUDIO_CODEC` | `aac` | Output audio codec |
| `AUDIO_BITRATE` | `128k` | Output audio bitrate |
| `AUDIO_CHANNELS` | `2` | Output audio channels |
| `OUTPUT_EXTENSION` | `.mkv` | Output container format |
| `SUFFIX` | `_JP` | Suffix appended to output filenames |
| `QUALITY` | `28` | CRF/quality (lower = better) |
| `EXTRA_ARGS` | `(empty)` | Extra ffmpeg arguments (e.g. `-map 0:m:language:spa`) |

## Project structure

```
h265ify/
├── .env.sample
├── .github/workflows/ci.yml
├── .gitignore
├── LICENSE
├── Makefile
├── pyproject.toml
├── README.md
├── src/
│   └── h265ify/
│       ├── __init__.py
│       ├── cli.py
│       └── transcoder.py
├── tests/
│   ├── __init__.py
│   └── test_transcoder.py
└── transcoder.py          # legacy standalone entry (for reference)
```

## Development

```bash
make dev         # install dev dependencies
make test        # run tests
make lint        # lint and format check
make format      # auto-format code
make clean       # remove virtualenv and caches
```
