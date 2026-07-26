import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

AUDIO_CODEC = os.getenv("AUDIO_CODEC", "aac")
AUDIO_BITRATE = os.getenv("AUDIO_BITRATE", "128k")
AUDIO_CHANNELS = os.getenv("AUDIO_CHANNELS", "2")
OUTPUT_EXTENSION = os.getenv("OUTPUT_EXTENSION", ".mkv")
QUALITY = os.getenv("QUALITY", "28")
SUFFIX = os.getenv("SUFFIX", "_JP")
EXTRA_ARGS = os.getenv("EXTRA_ARGS", "")

VIDEO_EXTENSIONS = (".mp4", ".mkv", ".avi", ".mov", ".ts", ".wmv", ".flv", ".webm")


def detect_hardware():
    """Detect available GPU HEVC encoders. Returns list of (label, encoder_name, quality_args)."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=15
        )
        out = result.stdout + result.stderr
    except Exception:
        print("Warning: Could not query ffmpeg encoders.")
        return []

    candidates = []

    if "hevc_nvenc" in out:
        candidates.append(
            (
                "nvidia_nvenc",
                "hevc_nvenc",
                ["-cq", QUALITY, "-rc", "vbr", "-preset", "p4", "-tune", "hq"],
            )
        )
    if "hevc_qsv" in out:
        candidates.append(
            ("intel_qsv", "hevc_qsv", ["-global_quality", QUALITY, "-preset", "medium"])
        )
    if "hevc_vaapi" in out:
        candidates.append(("vaapi", "hevc_vaapi", ["-global_quality", QUALITY]))
    if "hevc_mediacodec" in out:
        candidates.append(
            (
                "android_mediacodec",
                "hevc_mediacodec",
                ["-bitrate_mode", "cq", "-global_quality", QUALITY],
            )
        )

    return candidates


def get_codec(filepath):
    """Return video codec string, or empty string on failure."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_name",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(filepath),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        stderr = result.stderr.strip()
        if result.returncode != 0:
            raise RuntimeError(stderr or f"ffprobe returned {result.returncode}")
        return result.stdout.strip().lower()
    except Exception as e:
        raise RuntimeError(f"ffprobe failed for {filepath}: {e}")


def find_spanish_spain_stream(filepath):
    """Return stream index (e.g. '0:3') for best Spanish audio.
    Prefers Spain/Castellano titles, falls back to first Spanish stream.
    Returns None if no Spanish audio found."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a",
                "-show_entries",
                "stream=index:stream_tags=language,title",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(filepath),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception:
        return None

    raw = result.stdout.strip()
    if not raw:
        return None

    blocks = [b.strip() for b in raw.split("\n[/STREAM]")]
    spanish_streams = []
    spain_streams = []

    for block in blocks:
        lines = block.strip().split("\n")
        idx = None
        lang = None
        title = ""
        for line in lines:
            line = line.strip()
            if line.startswith("index="):
                idx = line.split("=", 1)[1].strip()
            elif line.startswith("TAG:language="):
                lang = line.split("=", 1)[1].strip().lower()
            elif line.startswith("TAG:title="):
                title = line.split("=", 1)[1].strip()

        if lang and lang.startswith("spa") and idx is not None:
            spanish_streams.append((idx, title))
            tlow = title.lower()
            if any(
                kw in tlow for kw in ("spain", "castellano", "es-es", "european spanish", "español")
            ):
                spain_streams.append((idx, title))

    if spain_streams:
        return int(spain_streams[0][0])
    if spanish_streams:
        return int(spanish_streams[0][0])
    return None


def main():
    parser = argparse.ArgumentParser(
        description="GPU-only HEVC/H.265 video transcoder. "
        "Detects available hardware and re-encodes videos in-place."
    )
    parser.add_argument("folder", type=str, help="Path to the folder containing video files")
    parser.add_argument(
        "--encoder",
        type=str,
        default=None,
        help="Force a specific encoder (e.g. hevc_nvenc, hevc_qsv, hevc_mediacodec)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be done without transcoding"
    )
    parser.add_argument(
        "-r", "--recursive", action="store_true", help="Process all subfolders recursively"
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete original files after successful transcode (instead of renaming to .to_delete)",
    )
    args = parser.parse_args()

    media_dir = args.folder
    if not os.path.isdir(media_dir):
        print(f"Error: Directory '{media_dir}' does not exist.")
        sys.exit(1)

    # ---- verify tools ----
    if not shutil.which("ffprobe"):
        print("Error: ffprobe not found. Install it:")
        print("  Debian/Ubuntu: sudo apt install ffprobe")
        print("  Fedora:        sudo dnf install ffprobe")
        print("  Termux:        pkg install ffprobe")
        print("  macOS:         brew install ffmpeg")
        sys.exit(3)
    if not shutil.which("ffmpeg"):
        print("Error: ffmpeg not found.")
        sys.exit(3)

    # ---- detect hardware ----
    if args.encoder:
        encoder_name = args.encoder
        quality_args = []
        print(f"Using forced encoder: {encoder_name}")
    else:
        available = detect_hardware()
        if not available:
            print("Error: No GPU HEVC encoder found in ffmpeg.")
            print("Install ffmpeg with hardware support:")
            print("  Linux (nvidia): ffmpeg with nvenc")
            print("  Linux (intel):   ffmpeg with qsv")
            print("  Termux/Android:  pkg install ffmpeg")
            sys.exit(2)

        print("Available GPU HEVC encoders:")
        for i, (label, enc, _) in enumerate(available, 1):
            print(f"  {i}. {label} ({enc})")
        print(f"  Selecting: {available[0][0]} ({available[0][1]})")
        _, encoder_name, quality_args = available[0]

    # ---- scan files ----
    all_files = []
    if args.recursive:
        for root, _, files in os.walk(media_dir):
            for f in files:
                all_files.append((root, f))
    else:
        for f in os.listdir(media_dir):
            if os.path.isfile(os.path.join(media_dir, f)):
                all_files.append((media_dir, f))
    all_files.sort(key=lambda x: x[1])

    for dirpath, filename in all_files:
        file_path = Path(os.path.join(dirpath, filename))
        ext_lower = file_path.suffix.lower()

        if ext_lower not in VIDEO_EXTENSIONS:
            continue

        stem = file_path.stem
        full_name = file_path.name

        # skip already-finished markers
        full_lower = full_name.lower()
        if ".processing." in full_lower or full_name.endswith(".to_delete"):
            continue

        # skip files already bearing the suffix (already encoded)
        if SUFFIX in stem:
            continue

        processing_path = os.path.join(dirpath, stem + SUFFIX + ".processing" + OUTPUT_EXTENSION)
        final_output = os.path.join(dirpath, stem + SUFFIX + OUTPUT_EXTENSION)
        to_delete_path = os.path.join(dirpath, full_name + ".to_delete")

        # skip if finished output already exists
        if os.path.exists(to_delete_path):
            print(f"Skipping {filename} — already done ({to_delete_path})")
            continue

        # if .processing exists from a previous interrupted run, discard and restart
        if os.path.exists(processing_path):
            print(
                f"  Removing incomplete .processing from previous run: {stem + SUFFIX + '.processing' + OUTPUT_EXTENSION}"
            )
            os.remove(processing_path)

        # skip if final output already exists (and is not the original itself)
        if os.path.exists(final_output) and final_output != str(file_path):
            print(f"Skipping {filename} — {stem + SUFFIX + OUTPUT_EXTENSION} already exists.")
            continue

        # ---- codec check ----
        try:
            codec = get_codec(file_path)
        except Exception as e:
            print(f"  Warning: {e}\n  Skipping — cannot probe file.")
            continue
        display = os.path.relpath(file_path, media_dir)
        print(f"\n--- {display} | {codec or 'unknown'} ---")

        if codec and codec in ("hevc", "h265"):
            print("  Already H.265 — skipping.")
            continue

        # ---- transcode: original → .processing ----
        if args.dry_run:
            print(
                f"  [DRY-RUN] Would transcode → {stem + SUFFIX + '.processing' + OUTPUT_EXTENSION}"
            )
            action = (
                "delete original"
                if args.delete
                else f"rename original → {full_name + '.to_delete'}"
            )
            print(f"  [DRY-RUN] Would {action}")
            print(f"  [DRY-RUN] Would rename processing → {stem + SUFFIX + OUTPUT_EXTENSION}")
            continue

        # ---- build ffmpeg command: original → .processing ----
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-i",
            str(file_path),
            "-c:v",
            encoder_name,
            "-c:a",
            AUDIO_CODEC,
            "-b:a",
            AUDIO_BITRATE,
            "-ac",
            str(AUDIO_CHANNELS),
        ]

        # encoder-specific quality args
        ffmpeg_cmd.extend(quality_args)

        if EXTRA_ARGS:
            extra_parts = EXTRA_ARGS.strip().split()
            # replace generic spanish map with specific best stream
            for j in range(len(extra_parts) - 1):
                if extra_parts[j] == "-map" and "m:language:spa" in extra_parts[j + 1]:
                    best = find_spanish_spain_stream(file_path)
                    if best is not None:
                        print(f"  Picked Spanish audio stream: 0:{best}")
                        extra_parts[j + 1] = f"0:{best}"
                    break
            ffmpeg_cmd.extend(extra_parts)

        ffmpeg_cmd.append(processing_path)

        print(f"  Transcoding: {filename} → {stem + SUFFIX + '.processing' + OUTPUT_EXTENSION}")
        print(f"  Encoder: {encoder_name}")
        print(f"  Command: {' '.join(ffmpeg_cmd)}")

        try:
            subprocess.run(ffmpeg_cmd, check=True)
        except subprocess.CalledProcessError:
            print(f"  Error: FFmpeg failed for {filename}.")
            if os.path.exists(processing_path):
                os.remove(processing_path)
            continue

        # ---- finalize ----
        os.rename(processing_path, final_output)
        if args.delete:
            os.remove(file_path)
            print(f"  ✓ Done — original deleted, created {stem + SUFFIX + OUTPUT_EXTENSION}\n")
        else:
            os.rename(file_path, to_delete_path)
            print(f"  ✓ Done — original renamed to {full_name + '.to_delete'}\n")

    print("All done.")


if __name__ == "__main__":
    main()
