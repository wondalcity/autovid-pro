"""Pillow-based thumbnail builder for Step 7.

Creates a YouTube-ready 1280×720 thumbnail by compositing a scene image
with a text overlay. No external API required — uses Pillow only.

Design
------
  - Full-bleed scene image as background
  - Bottom gradient overlay for text legibility
  - Large title text (Korean-capable system font)
  - Subtle top bar for visual framing

Fonts tried in order (first one found is used):
  macOS: AppleGothic → Osaka → Helvetica
  Linux: NanumGothic → DejaVuSans
"""
import io
import logging
import textwrap
from pathlib import Path

logger = logging.getLogger(__name__)

_WIDTH = 1280
_HEIGHT = 720

# Font search paths — ordered by preference
_FONT_CANDIDATES = [
    # macOS Korean fonts
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    "/System/Library/Fonts/Supplemental/AppleMyungjo.ttf",
    "/Library/Fonts/NanumGothic.ttf",
    "/Library/Fonts/NanumGothicBold.ttf",
    # Linux Korean fonts
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    # macOS fallback
    "/System/Library/Fonts/Helvetica.ttc",
]


def _find_font(size: int):
    """Return an ImageFont, trying Korean-capable fonts first."""
    from PIL import ImageFont
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def build_thumbnail(
    scene_image_bytes: bytes,
    title: str,
    style: str = "bold",
) -> bytes:
    """Composite a scene image with title text to produce a 1280×720 thumbnail.

    Args:
        scene_image_bytes: PNG/JPEG bytes of a scene image (from Step 5).
        title:             YouTube video title (Korean or English).
        style:             "bold" | "minimal" | "gradient"

    Returns:
        PNG bytes of the finished thumbnail.
    """
    from PIL import Image, ImageDraw, ImageFilter

    # ── 1. Load & resize scene image ──────────────────────────────────────────
    bg = Image.open(io.BytesIO(scene_image_bytes)).convert("RGB")
    bg = bg.resize((_WIDTH, _HEIGHT), Image.LANCZOS)

    # ── 2. Style-specific overlay ─────────────────────────────────────────────
    overlay = Image.new("RGBA", (_WIDTH, _HEIGHT), (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(overlay)

    if style == "minimal":
        # Light semi-transparent bottom strip
        for y in range(_HEIGHT - 160, _HEIGHT):
            alpha = int(180 * (y - (_HEIGHT - 160)) / 160)
            draw_ov.rectangle([(0, y), (_WIDTH, y + 1)], fill=(0, 0, 0, alpha))
    elif style == "gradient":
        # Full-height gradient from transparent top to dark bottom
        for y in range(0, _HEIGHT):
            alpha = int(180 * (y / _HEIGHT) ** 2)
            draw_ov.rectangle([(0, y), (_WIDTH, y + 1)], fill=(0, 0, 30, alpha))
    else:  # "bold" (default) — strong bottom half darkening
        for y in range(_HEIGHT // 2, _HEIGHT):
            alpha = int(220 * ((y - _HEIGHT // 2) / (_HEIGHT // 2)) ** 0.7)
            draw_ov.rectangle([(0, y), (_WIDTH, y + 1)], fill=(0, 0, 0, alpha))
        # Red/orange accent bar at top
        draw_ov.rectangle([(0, 0), (_WIDTH, 8)], fill=(220, 50, 50, 230))

    bg = bg.convert("RGBA")
    bg = Image.alpha_composite(bg, overlay).convert("RGB")

    # ── 3. Title text ──────────────────────────────────────────────────────────
    draw = ImageDraw.Draw(bg)

    # Wrap title to ~22 chars per line so it fits
    wrapped = textwrap.fill(title, width=22)
    lines = wrapped.split("\n")

    font_size = 72 if len(lines) == 1 else 60
    font = _find_font(font_size)
    small_font = _find_font(36)

    # Calculate total text block height
    try:
        line_h = font.getbbox("가나다")[3] + 10
    except Exception:
        line_h = font_size + 10
    block_h = line_h * len(lines)

    y_start = _HEIGHT - block_h - 50

    # Shadow pass
    for i, line in enumerate(lines):
        y = y_start + i * line_h
        try:
            bbox = font.getbbox(line)
            text_w = bbox[2] - bbox[0]
        except Exception:
            text_w = len(line) * font_size * 0.6
        x = (_WIDTH - text_w) // 2
        for dx, dy in [(-2, -2), (2, -2), (-2, 2), (2, 2)]:
            draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0))

    # Main text pass (white)
    for i, line in enumerate(lines):
        y = y_start + i * line_h
        try:
            bbox = font.getbbox(line)
            text_w = bbox[2] - bbox[0]
        except Exception:
            text_w = len(line) * font_size * 0.6
        x = (_WIDTH - text_w) // 2
        draw.text((x, y), line, font=font, fill=(255, 255, 255))

    # ── 4. Save ───────────────────────────────────────────────────────────────
    buf = io.BytesIO()
    bg.save(buf, format="PNG", optimize=True)
    logger.info(
        f"[thumbnail] Built {_WIDTH}×{_HEIGHT} thumbnail "
        f"({len(buf.getvalue()) // 1024} KB) style={style!r}"
    )
    return buf.getvalue()
