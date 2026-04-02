"""Image-to-video generation utility.

Supported providers (configure via env vars)
--------------------------------------------
RUNWAY_API_KEY   — Runway ML Gen-3 Alpha Turbo (cloud)
SVD_SERVER_URL   — Local Stable Video Diffusion via Gradio/ComfyUI
                   e.g. http://localhost:7860

If neither key is present, generate_video() raises NotImplementedError and
Step 5 will gracefully skip video creation while still saving images.

Env vars
--------
RUNWAY_API_KEY   — enables Runway ML
SVD_SERVER_URL   — e.g. "http://localhost:7860"  (enables local SVD)
VIDEO_PROVIDER   — "runway" (default if key set) | "svd"
"""
import asyncio
import base64
import logging
import os

import httpx

from app.utils.settings_store import get as _cfg

logger = logging.getLogger(__name__)

_SVD_URL = os.getenv("SVD_SERVER_URL", "")

_RUNWAY_BASE = "https://api.dev.runwayml.com/v1"
_RUNWAY_HEADERS = {
    "X-Runway-Version": "2024-11-06",
    "Content-Type": "application/json",
}


# ─── Runway ML ────────────────────────────────────────────────────────────────

async def _generate_via_runway(
    image_bytes: bytes,
    video_prompt: str,
    duration_seconds: int,
) -> bytes:
    """Generate a video clip via Runway ML Gen-3 Alpha Turbo.

    Calls /image_to_video, then polls /tasks/{id} until SUCCEEDED.
    Timeout: 3 minutes.
    """
    runway_key = _cfg("RUNWAY_API_KEY")
    image_b64 = base64.b64encode(image_bytes).decode()

    async with httpx.AsyncClient(timeout=30) as client:
        # ── Submit task ──────────────────────────────────────────────────
        submit_resp = await client.post(
            f"{_RUNWAY_BASE}/image_to_video",
            headers={**_RUNWAY_HEADERS, "Authorization": f"Bearer {runway_key}"},
            json={
                "model": "gen3a_turbo",
                "promptImage": f"data:image/png;base64,{image_b64}",
                "promptText": video_prompt,
                "duration": min(max(duration_seconds, 5), 10),
                "ratio": "1280:768",
            },
        )
        submit_resp.raise_for_status()
        task_id: str = submit_resp.json()["id"]
        logger.info(f"[runway] Task submitted: {task_id}")

    # ── Poll for completion (max 3 min) ──────────────────────────────────
    async with httpx.AsyncClient(timeout=30) as client:
        for attempt in range(90):  # 90 × 2 s = 3 min
            await asyncio.sleep(2)
            poll_resp = await client.get(
                f"{_RUNWAY_BASE}/tasks/{task_id}",
                headers={"Authorization": f"Bearer {runway_key}"},
            )
            poll_resp.raise_for_status()
            task = poll_resp.json()
            status = task.get("status", "")

            if status == "SUCCEEDED":
                video_url: str = task["output"][0]
                logger.info(f"[runway] Task {task_id} succeeded → {video_url}")
                video_resp = await client.get(video_url, timeout=60)
                video_resp.raise_for_status()
                return video_resp.content

            if status == "FAILED":
                raise RuntimeError(
                    f"Runway task {task_id} failed: {task.get('failure', 'unknown')}"
                )

            if attempt % 10 == 0:
                logger.info(f"[runway] Task {task_id} still {status} …")

    raise TimeoutError(f"Runway task {task_id} did not complete within 3 minutes")


# ─── Local SVD (Stable Video Diffusion via Gradio) ────────────────────────────

async def _generate_via_svd(
    image_bytes: bytes,
    video_prompt: str,
    duration_seconds: int,
) -> bytes:
    """Generate a video clip from a local Stable Video Diffusion Gradio server.

    Expects the server to expose a POST endpoint at {SVD_SERVER_URL}/api/generate
    accepting:
        { "image": "<base64>", "motion_bucket_id": 127, "fps": 6, "num_frames": N }
    and returning:
        { "video": "<base64 mp4>" }

    Adjust the endpoint and payload to match your specific SVD Gradio setup.
    """
    image_b64 = base64.b64encode(image_bytes).decode()
    num_frames = duration_seconds * 6  # 6 fps

    logger.info(
        f"[svd] Requesting {num_frames} frames from {_SVD_URL}"
    )
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            f"{_SVD_URL}/api/generate",
            json={
                "image": image_b64,
                "motion_bucket_id": 100,  # 0-255: higher = more motion
                "fps": 6,
                "num_frames": num_frames,
                "noise_aug_strength": 0.02,
            },
        )
        resp.raise_for_status()
        result = resp.json()

    if "video" not in result:
        raise RuntimeError(
            f"SVD server response missing 'video' key. Got: {list(result.keys())}"
        )
    logger.info("[svd] Video received from local SVD server")
    return base64.b64decode(result["video"])


# ─── Public API ───────────────────────────────────────────────────────────────

async def generate_video(
    image_bytes: bytes,
    video_prompt: str,
    duration_seconds: int = 5,
    provider_override: str = "",
) -> bytes:
    """Generate a short video clip from a still image.

    Args:
        image_bytes:       Source image (PNG/JPEG bytes).
        video_prompt:      Camera movement / motion description.
        duration_seconds:  Target clip length in seconds (3–10 s recommended).
        provider_override: "runway" | "svd" | "none" | "" (auto-detect).
                           "none" skips video generation entirely.

    Returns:
        MP4 video bytes.

    Raises:
        NotImplementedError: If provider is "none", not configured, or no key set.
        RuntimeError:        If the provider call fails.
    """
    selected = (provider_override or "").lower()

    if selected == "none":
        raise NotImplementedError("Video generation disabled by user selection.")

    runway_key = _cfg("RUNWAY_API_KEY")
    if selected == "runway" or (not selected and runway_key):
        if not runway_key:
            raise NotImplementedError("RUNWAY_API_KEY is not set.")
        return await _generate_via_runway(image_bytes, video_prompt, duration_seconds)

    if selected == "svd" or (not selected and _SVD_URL):
        if not _SVD_URL:
            raise NotImplementedError("SVD_SERVER_URL is not set.")
        return await _generate_via_svd(image_bytes, video_prompt, duration_seconds)

    raise NotImplementedError(
        "Video generation not configured. "
        "Set RUNWAY_API_KEY (Runway ML) or SVD_SERVER_URL (local SVD) in .env, "
        "or set video_provider to 'none' to skip."
    )
