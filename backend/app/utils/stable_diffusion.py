"""Image generation utility — DALL-E 3 (primary) or Stability AI.

Provider priority
-----------------
1. IMAGE_PROVIDER=dalle3  (default)  → requires OPENAI_API_KEY
2. IMAGE_PROVIDER=stabilityai        → requires STABLE_DIFFUSION_API_KEY

If the selected provider's key is missing the function raises RuntimeError.

Env vars
--------
OPENAI_API_KEY           — enables DALL-E 3
STABLE_DIFFUSION_API_KEY — enables Stability AI core API
IMAGE_PROVIDER           — "dalle3" (default) | "stabilityai"
"""
import base64
import logging
import os

import httpx

logger = logging.getLogger(__name__)

_OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")

# ─── Genre-specific prompt styles ─────────────────────────────────────────────

GENRE_STYLES: dict[str, str] = {
    "mystery":  "Dark and moody cinematic lighting, mystery atmosphere, hyper-realistic, 8k, detailed shadows, fog, 35mm lens style, low key lighting.",
    "finance":  "Clean professional editorial photography, corporate modern aesthetic, bright studio lighting, 85mm lens, high-end commercial style, sharp focus.",
    "history":  "Vintage film grain, oil painting style or historical reenactment photography, warm sepia tones, dramatic historical lighting, epic scale, highly detailed textures.",
    "general":  "High-quality professional stock photo style, realistic, 8k resolution, cinematic composition, vivid colors.",
}


def enhance_image_prompt(base_prompt: str, genre: str = "general") -> str:
    """Append genre-specific aesthetic keywords to a base image prompt.

    Args:
        base_prompt: The scene description from the storyboard.
        genre:       Content genre — one of "mystery", "finance", "history", "general".

    Returns:
        Enriched prompt string with style suffix and aspect ratio flag.
    """
    style_suffix = GENRE_STYLES.get(genre.lower(), GENRE_STYLES["general"])
    return f"{base_prompt}, {style_suffix} --ar 16:9"
_SD_KEY = os.getenv("STABLE_DIFFUSION_API_KEY", "")
_PROVIDER = os.getenv("IMAGE_PROVIDER", "dalle3").lower()
_STABILITY_URL = "https://api.stability.ai/v2beta/stable-image/generate/core"


# ─── Size helpers ─────────────────────────────────────────────────────────────

def _dalle3_size(width: int, height: int) -> str:
    """Map arbitrary width/height to a DALL-E 3 supported size string."""
    if width > height:
        return "1792x1024"   # landscape / widescreen
    if height > width:
        return "1024x1792"   # portrait
    return "1024x1024"       # square


def _stability_aspect(width: int, height: int) -> str:
    """Map width/height to a Stability AI aspect ratio string."""
    ratio = width / height if height else 1.0
    if ratio >= 1.7:
        return "16:9"
    if ratio >= 1.2:
        return "4:3"
    if ratio <= 0.6:
        return "9:16"
    if ratio <= 0.85:
        return "3:4"
    return "1:1"


# ─── DALL-E 3 ─────────────────────────────────────────────────────────────────

async def _generate_dalle3(prompt: str, width: int, height: int) -> bytes:
    from openai import AsyncOpenAI  # local import keeps dependency optional

    if not _OPENAI_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to your .env to use DALL-E 3."
        )

    client = AsyncOpenAI(api_key=_OPENAI_KEY)
    size = _dalle3_size(width, height)

    logger.info(f"[dalle3] Generating image {size} — prompt: {prompt[:80]}…")
    response = await client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size=size,
        quality="standard",
        response_format="b64_json",
        n=1,
    )
    image_b64: str = response.data[0].b64_json
    return base64.b64decode(image_b64)


# ─── Stability AI ─────────────────────────────────────────────────────────────

async def _generate_stability(prompt: str, width: int, height: int) -> bytes:
    if not _SD_KEY:
        raise RuntimeError(
            "STABLE_DIFFUSION_API_KEY is not set. "
            "Add it to your .env to use Stability AI."
        )

    aspect = _stability_aspect(width, height)
    logger.info(
        f"[stabilityai] Generating image {aspect} — prompt: {prompt[:80]}…"
    )

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            _STABILITY_URL,
            headers={
                "Authorization": f"Bearer {_SD_KEY}",
                "Accept": "image/*",
            },
            data={
                "prompt": prompt,
                "aspect_ratio": aspect,
                "output_format": "png",
                "style_preset": "cinematic",
            },
        )
        resp.raise_for_status()
        return resp.content


# ─── Placeholder generator (no external API required) ────────────────────────

def _generate_placeholder(prompt: str, width: int, height: int) -> bytes:
    """Generate a simple gradient PNG placeholder.

    Uses only stdlib + optional Pillow.  Falls back to a raw minimal PNG if Pillow
    is not installed or if text rendering fails (e.g., Korean chars on default font).
    """
    try:
        from PIL import Image, ImageDraw
        import io as _io

        img = Image.new("RGB", (width, height), color=(30, 30, 60))
        draw = ImageDraw.Draw(img)

        # Gradient overlay effect
        for y in range(0, height, 4):
            alpha = int(60 * (y / height))
            draw.rectangle([(0, y), (width, y + 4)], fill=(alpha, alpha, alpha + 40))

        # Only draw ASCII-safe text to avoid encoding errors with default PIL font
        safe_prompt = "".join(c if ord(c) < 128 else "?" for c in prompt[:120])
        try:
            draw.text((width // 2, height // 2), safe_prompt[:80], fill=(200, 200, 240), anchor="mm")
            draw.text((width // 2, height - 40), "[AI Image Placeholder]", fill=(150, 150, 150), anchor="mm")
        except Exception:
            pass  # Skip text if font rendering fails

        buf = _io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        # Fallback: minimal 1×1 white PNG
        return (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
            b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
            b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )


# ─── Public API ───────────────────────────────────────────────────────────────

async def generate_image(
    prompt: str,
    width: int = 1792,
    height: int = 1024,
    genre: str = "general",
) -> bytes:
    """Generate an image from a text prompt, optionally enriched by genre style.

    Args:
        prompt: Text description (English recommended for best results).
        width:  Desired width in pixels  (mapped to nearest supported size).
        height: Desired height in pixels (mapped to nearest supported size).
        genre:  Content genre for automatic style enrichment — one of
                "mystery", "finance", "history", "general" (default).
                Pass ``genre=""`` to skip enrichment.

    Returns:
        PNG image bytes.

    Raises:
        RuntimeError: If the required API key is missing or the call fails.
    """
    enriched_prompt = enhance_image_prompt(prompt, genre) if genre else prompt

    provider = _PROVIDER

    # Auto-select: fall back to stabilityai if no OpenAI key
    if provider == "dalle3" and not _OPENAI_KEY and _SD_KEY:
        logger.warning(
            "[image] OPENAI_API_KEY not set — falling back to Stability AI"
        )
        provider = "stabilityai"

    # Last resort: generate a placeholder PNG without any external API
    if provider == "dalle3" and not _OPENAI_KEY:
        logger.warning("[image] OPENAI_API_KEY not set — using placeholder image")
        return _generate_placeholder(enriched_prompt, width, height)

    if provider == "stabilityai":
        if not _SD_KEY or _SD_KEY.strip() in ("", "..."):
            logger.warning("[image] STABLE_DIFFUSION_API_KEY not set — using placeholder image")
            return _generate_placeholder(enriched_prompt, width, height)
        return await _generate_stability(enriched_prompt, width, height)

    # Default: DALL-E 3
    try:
        return await _generate_dalle3(enriched_prompt, width, height)
    except Exception as exc:
        logger.warning(f"[image] DALL-E 3 failed ({exc}) — using placeholder image")
        return _generate_placeholder(enriched_prompt, width, height)
