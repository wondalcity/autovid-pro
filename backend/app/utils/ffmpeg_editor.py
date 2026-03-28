"""FFmpeg-based video editing utility for Step 6.

System requirements
-------------------
  macOS:  brew install ffmpeg
  Ubuntu: sudo apt install ffmpeg

Pipeline
--------
  1. Download all assets (voice MP3, caption SRT, video/image clips) via httpx
  2. Per-scene: use video clip if available, else convert image → still clip
  3. Concatenate all clips (re-encode to uniform H.264 30fps 1920×1080)
  4. Replace audio track with TTS voice (AAC 192k)
  5. Add subtitles — soft-coded (default) or hard burn-in
  6. Return final MP4 as bytes

All ffmpeg work happens inside a TemporaryDirectory that is cleaned up
automatically when build_final_video() returns.
"""
import asyncio
import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Unified output resolution — change here to affect all scenes
_RESOLUTION = "1920x1080"
_FPS = "30"
_VIDEO_CODEC = ["libx264", "-preset", "fast", "-crf", "23"]


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _check_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg is not installed or not on PATH.\n"
            "  macOS:  brew install ffmpeg\n"
            "  Ubuntu: sudo apt install ffmpeg"
        )


def _run(cmd: list[str]) -> None:
    """Execute a shell command, raising RuntimeError on non-zero exit."""
    logger.debug("[ffmpeg] %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed (exit {result.returncode}): {' '.join(cmd)}\n"
            f"{result.stderr[-3000:]}"
        )


async def _run_async(cmd: list[str]) -> None:
    """Run a blocking subprocess in a thread so the event loop isn't blocked."""
    await asyncio.to_thread(_run, cmd)


# ─── File download ────────────────────────────────────────────────────────────

async def download_file(url: str, dest: Path) -> None:
    """Download a URL to dest, following redirects."""
    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
    logger.info(
        "[ffmpeg] ↓ %s → %s (%s B)",
        url[:60],
        dest.name,
        f"{dest.stat().st_size:,}",
    )


# ─── Timestamp parser ─────────────────────────────────────────────────────────

def parse_scene_duration(timestamp: str, default: float = 5.0) -> float:
    """Convert "00:00 - 00:15" or "0:00-1:30" → duration in seconds.

    Returns `default` if the timestamp cannot be parsed.
    """
    def _to_sec(t: str) -> float:
        parts = t.strip().split(":")
        try:
            if len(parts) == 2:
                return int(parts[0]) * 60 + float(parts[1])
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        except (ValueError, IndexError):
            pass
        return default

    m = re.match(r"(.+?)\s*[-–]\s*(.+)", timestamp.strip())
    if not m:
        return default
    start = _to_sec(m.group(1))
    end = _to_sec(m.group(2))
    return max(end - start, 1.0)


# ─── Per-clip generation ──────────────────────────────────────────────────────

async def image_to_clip(
    image_path: Path,
    duration: float,
    output_path: Path,
) -> None:
    """Convert a still image to an H.264 video clip of `duration` seconds.

    Applies a subtle Ken Burns zoom (1x → 1.06x) for visual interest.
    Falls back to a static frame if the zoom filter fails.
    """
    zoom_filter = (
        f"scale=8000:-1,"
        f"zoompan=z='min(zoom+0.0008,1.06)':d={int(duration * int(_FPS))}:"
        f"s={_RESOLUTION},setsar=1,setpts=PTS-STARTPTS"
    )
    try:
        await _run_async([
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", str(image_path),
            "-vf", zoom_filter,
            "-t", str(duration),
            "-c:v", *_VIDEO_CODEC,
            "-r", _FPS,
            "-pix_fmt", "yuv420p",
            str(output_path),
        ])
    except RuntimeError:
        # Fallback: simple scale + pad without zoom
        logger.warning(
            "[ffmpeg] zoompan failed for %s — using static frame", image_path.name
        )
        await _run_async([
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", str(image_path),
            "-vf", (
                f"scale={_RESOLUTION}:force_original_aspect_ratio=decrease,"
                f"pad={_RESOLUTION}:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
            ),
            "-t", str(duration),
            "-c:v", *_VIDEO_CODEC,
            "-r", _FPS,
            "-pix_fmt", "yuv420p",
            str(output_path),
        ])
    logger.info("[ffmpeg] image→clip: %s (%.1fs)", output_path.name, duration)


async def black_clip(duration: float, output_path: Path) -> None:
    """Generate a solid-black video clip as a placeholder."""
    await _run_async([
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c=black:s={_RESOLUTION}:r={_FPS}:d={duration}",
        "-c:v", *_VIDEO_CODEC,
        "-pix_fmt", "yuv420p",
        str(output_path),
    ])
    logger.info("[ffmpeg] black clip: %s (%.1fs)", output_path.name, duration)


async def normalise_clip(input_path: Path, output_path: Path) -> None:
    """Re-encode a downloaded video clip to the project standard (1920×1080 H.264 30fps).

    This ensures all clips have the same parameters before concatenation.
    """
    await _run_async([
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vf", (
            f"scale={_RESOLUTION}:force_original_aspect_ratio=decrease,"
            f"pad={_RESOLUTION}:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
        ),
        "-c:v", *_VIDEO_CODEC,
        "-r", _FPS,
        "-pix_fmt", "yuv420p",
        "-an",          # strip audio — will be replaced by TTS
        str(output_path),
    ])


# ─── Concatenation ────────────────────────────────────────────────────────────

async def concat_clips(
    clip_paths: list[Path],
    output_path: Path,
    tmpdir: Path,
) -> None:
    """Concatenate clips using the FFmpeg concat demuxer.

    Clips must already be in a uniform format (same codec/resolution/fps).
    """
    list_file = tmpdir / "concat_list.txt"
    list_file.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in clip_paths),
        encoding="utf-8",
    )
    await _run_async([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",   # stream-copy (all clips are already uniform)
        str(output_path),
    ])
    logger.info(
        "[ffmpeg] concat: %d clips → %s", len(clip_paths), output_path.name
    )


# ─── Audio merge ──────────────────────────────────────────────────────────────

async def merge_audio(
    video_path: Path,
    audio_path: Path,
    output_path: Path,
) -> None:
    """Replace the video's audio track with the TTS voice file.

    `-shortest` trims to whichever is shorter (video or audio).
    """
    await _run_async([
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        str(output_path),
    ])
    logger.info("[ffmpeg] audio merged → %s", output_path.name)


# ─── Subtitle attachment ──────────────────────────────────────────────────────

async def add_subtitles(
    video_path: Path,
    srt_path: Path,
    output_path: Path,
    burn_in: bool = False,
) -> None:
    """Attach the SRT subtitle file.

    burn_in=False (default): soft-coded (stream copy, toggleable in player)
    burn_in=True:            hard-coded (re-encode, always visible)
    """
    if burn_in:
        # Escape path for libass (Windows backslash / drive letter)
        srt_esc = str(srt_path).replace("\\", "/").replace(":", "\\\\:")
        await _run_async([
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", (
                f"subtitles={srt_esc}:"
                "force_style='FontSize=18,FontName=Arial,"
                "PrimaryColour=&H00FFFFFF,"
                "OutlineColour=&H00000000,Outline=2,Shadow=1'"
            ),
            "-c:v", *_VIDEO_CODEC,
            "-c:a", "copy",
            str(output_path),
        ])
    else:
        await _run_async([
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(srt_path),
            "-c:v", "copy",
            "-c:a", "copy",
            "-c:s", "mov_text",         # MP4 subtitle track
            "-metadata:s:s:0", "language=kor",
            str(output_path),
        ])
    logger.info(
        "[ffmpeg] subtitles (%s) → %s",
        "burn-in" if burn_in else "soft",
        output_path.name,
    )


# ─── Main orchestrator ────────────────────────────────────────────────────────

async def build_final_video(
    voice_url: str,
    caption_url: Optional[str],
    video_rows: list[dict],     # assets rows: {scene_id, file_path, metadata}
    image_rows: list[dict],     # fallback image rows
    storyboard_rows: list[dict],# for timestamp → duration
    burn_subtitles: bool = False,
) -> bytes:
    """Orchestrate the full editing pipeline and return final MP4 bytes.

    Precedence per scene:  video clip  >  image still  >  black placeholder
    """
    _check_ffmpeg()

    with tempfile.TemporaryDirectory() as _tmp:
        tmpdir = Path(_tmp)
        logger.info("[ffmpeg] Temp dir: %s", tmpdir)

        # ── Download voice & caption ────────────────────────────────────────
        voice_path = tmpdir / "voice.mp3"
        await download_file(voice_url, voice_path)

        srt_path: Optional[Path] = None
        if caption_url:
            srt_path = tmpdir / "captions.srt"
            await download_file(caption_url, srt_path)

        # ── Build lookup maps ───────────────────────────────────────────────
        sb_map = {row["scene_id"]: row for row in storyboard_rows}
        vid_map = {row["scene_id"]: row for row in video_rows}
        img_map = {row["scene_id"]: row for row in image_rows}
        all_nums = sorted(
            set(sb_map) | set(vid_map) | set(img_map)
        )

        if not all_nums:
            raise RuntimeError(
                "No scene media found (no images or video clips). "
                "Run Step 4 (storyboard) and Step 5 (images/video) first."
            )

        # ── Per-scene: download + normalise / convert ───────────────────────
        clip_paths: list[Path] = []

        for i, num in enumerate(all_nums):
            sb_row = sb_map.get(num, {})
            ts = (sb_row.get("metadata") or {}).get("timestamp", "")
            duration = parse_scene_duration(ts, default=5.0)

            norm_path = tmpdir / f"norm_{i:03d}.mp4"

            if num in vid_map and vid_map[num].get("file_path"):
                raw_path = tmpdir / f"raw_vid_{i:03d}.mp4"
                await download_file(vid_map[num]["file_path"], raw_path)
                await normalise_clip(raw_path, norm_path)

            elif num in img_map and img_map[num].get("file_path"):
                img_path = tmpdir / f"img_{i:03d}.png"
                await download_file(img_map[num]["file_path"], img_path)
                await image_to_clip(img_path, duration, norm_path)

            else:
                logger.warning(
                    "[ffmpeg] No media for scene %s — inserting black clip", num
                )
                await black_clip(duration, norm_path)

            if norm_path.exists() and norm_path.stat().st_size > 0:
                clip_paths.append(norm_path)

        logger.info("[ffmpeg] %d scene clips ready", len(clip_paths))

        # ── Concatenate ─────────────────────────────────────────────────────
        concat_path = tmpdir / "concat.mp4"
        await concat_clips(clip_paths, concat_path, tmpdir)

        # ── Merge TTS audio ─────────────────────────────────────────────────
        with_audio_path = tmpdir / "with_audio.mp4"
        await merge_audio(concat_path, voice_path, with_audio_path)

        # ── Add subtitles ────────────────────────────────────────────────────
        if srt_path and srt_path.exists() and srt_path.stat().st_size > 0:
            final_path = tmpdir / "final.mp4"
            await add_subtitles(with_audio_path, srt_path, final_path, burn_in=burn_subtitles)
        else:
            logger.warning("[ffmpeg] No caption file — skipping subtitle step")
            final_path = with_audio_path

        file_size = final_path.stat().st_size
        logger.info(
            "[ffmpeg] Final video ready: %s (%s MB)",
            final_path.name,
            f"{file_size / 1_048_576:.1f}",
        )
        return final_path.read_bytes()
