"""Image generation utility — DALL-E 3, Gemini Imagen 3, or Stability AI.

Provider priority (IMAGE_PROVIDER env var)
------------------------------------------
1. "dalle3"      (default) → OPENAI_API_KEY
2. "gemini"                → GOOGLE_AI_API_KEY  (Imagen 3)
3. "stabilityai"           → STABLE_DIFFUSION_API_KEY
4. "auto"                  → tries all available providers in order

Auto-fallback chain (always active):
  Primary provider → next available provider → placeholder PNG

Env vars
--------
OPENAI_API_KEY           — enables DALL-E 3
GOOGLE_AI_API_KEY        — enables Gemini Imagen 3 (Google AI Studio)
STABLE_DIFFUSION_API_KEY — enables Stability AI core API
IMAGE_PROVIDER           — "dalle3" (default) | "gemini" | "stabilityai" | "auto"
"""
import base64
import logging

import httpx

from app.utils.settings_store import get as _cfg

logger = logging.getLogger(__name__)

_STABILITY_URL = "https://api.stability.ai/v2beta/stable-image/generate/core"

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

    key = _cfg("OPENAI_API_KEY")
    if not key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to your .env to use DALL-E 3."
        )

    client = AsyncOpenAI(api_key=key)
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
    key = _cfg("STABLE_DIFFUSION_API_KEY")
    if not key:
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
                "Authorization": f"Bearer {key}",
                "Accept": "image/*",
            },
            # Stability AI v2beta requires multipart/form-data — use files= not data=
            files={
                "prompt": (None, prompt[:2000]),
                "aspect_ratio": (None, aspect),
                "output_format": (None, "png"),
            },
        )
        if not resp.is_success:
            body = resp.text[:300]
            raise RuntimeError(f"Stability AI {resp.status_code}: {body}")
        return resp.content


# ─── Gemini Imagen 3 ──────────────────────────────────────────────────────────

def _gemini_aspect(width: int, height: int) -> str:
    ratio = width / height if height else 1.0
    if ratio >= 1.6:
        return "16:9"
    if ratio >= 1.2:
        return "4:3"
    if ratio <= 0.65:
        return "9:16"
    if ratio <= 0.85:
        return "3:4"
    return "1:1"


async def _generate_gemini(prompt: str, width: int, height: int) -> bytes:
    """Generate an image via Google Gemini (google-genai SDK).

    Tries Imagen 4 (paid) first, falls back to gemini-2.0-flash-exp (free tier).
    """
    key = _cfg("GOOGLE_AI_API_KEY")
    if not key:
        raise RuntimeError("GOOGLE_AI_API_KEY is not set.")

    import asyncio
    from google import genai

    loop = asyncio.get_event_loop()
    client = genai.Client(api_key=key)

    aspect = _gemini_aspect(width, height)
    logger.info(f"[gemini] Generating image {aspect} — prompt: {prompt[:80]}…")

    # ── Try Imagen 4 (paid plan) ──────────────────────────────────────────────
    try:
        from google.genai.types import GenerateImagesConfig

        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_images(
                model="imagen-4.0-generate-001",
                prompt=prompt,
                config=GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio=aspect,
                    output_mime_type="image/png",
                ),
            ),
        )
        if response.generated_images:
            return response.generated_images[0].image.image_bytes
    except Exception as exc:
        logger.info(f"[gemini] Imagen 4 unavailable ({exc.__class__.__name__}: {str(exc)[:80]}) — trying gemini-2.0-flash-exp")

    # ── Fallback: gemini-2.5-flash-image via generate_content (paid plan) ──
    from google.genai import types as genai_types

    def _flash_generate() -> bytes:
        resp = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=prompt[:800],
            config=genai_types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            ),
        )
        for part in resp.candidates[0].content.parts:
            if part.inline_data is not None:
                return part.inline_data.data
        raise RuntimeError("gemini-2.5-flash-image returned no image parts")

    return await loop.run_in_executor(None, _flash_generate)


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
    provider_override: str = "",
) -> bytes:
    """Generate an image with automatic provider fallback.

    Provider order is determined by IMAGE_PROVIDER env var or provider_override.
    If the primary provider fails (quota, billing, etc.) the next available
    provider is tried automatically before falling back to a placeholder PNG.

    Fallback chain:
      dalle3      → gemini → stabilityai → placeholder
      gemini      → dalle3 → stabilityai → placeholder
      stabilityai → dalle3 → gemini      → placeholder
      auto        → dalle3 → gemini      → stabilityai → placeholder
    """
    enriched_prompt = enhance_image_prompt(prompt, genre) if genre else prompt

    # Build ordered list of providers to try
    selected = (provider_override or _cfg("IMAGE_PROVIDER", "dalle3") or "dalle3").lower()

    _ALL = ["dalle3", "gemini", "stabilityai"]
    # Start with selected, then try others in default order
    order = [selected] + [p for p in _ALL if p != selected]

    # Filter to providers that have keys configured (checked at call time)
    def _has_key(p: str) -> bool:
        if p == "dalle3":      return bool(_cfg("OPENAI_API_KEY"))
        if p == "gemini":      return bool(_cfg("GOOGLE_AI_API_KEY"))
        if p == "stabilityai":
            k = _cfg("STABLE_DIFFUSION_API_KEY")
            return bool(k and k.strip() not in ("", "..."))
        return False

    available = [p for p in order if _has_key(p)]

    if not available:
        logger.warning("[image] No image provider keys configured — using placeholder")
        return _generate_placeholder(enriched_prompt, width, height)

    for provider in available:
        try:
            if provider == "dalle3":
                return await _generate_dalle3(enriched_prompt, width, height)
            elif provider == "gemini":
                return await _generate_gemini(enriched_prompt, width, height)
            elif provider == "stabilityai":
                return await _generate_stability(enriched_prompt, width, height)
        except Exception as exc:
            next_p = available[available.index(provider) + 1] if provider != available[-1] else "placeholder"
            logger.warning(f"[image] {provider} failed ({exc.__class__.__name__}: {str(exc)[:120]}) — trying {next_p}")

    logger.warning("[image] All providers exhausted — using placeholder")
    return _generate_placeholder(enriched_prompt, width, height)
