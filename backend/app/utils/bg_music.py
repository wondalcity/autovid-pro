"""Background music utility — downloads CC0 tracks from Pixabay Music API.

Pixabay Music tracks are CC0 licensed: no copyright claims on YouTube.

Setup
-----
1. Register free at https://pixabay.com/api/docs/
2. Add PIXABAY_API_KEY=your_key to .env

Genre → search query mapping
-----------------------------
general  → "ambient background"
finance  → "corporate upbeat"
mystery  → "dark suspense"
history  → "cinematic orchestral"
"""
import logging

import httpx

from app.utils.settings_store import get as _cfg

logger = logging.getLogger(__name__)
_API_URL = "https://pixabay.com/api/music/"

GENRE_QUERIES: dict[str, str] = {
    "general": "ambient background",
    "finance": "corporate upbeat",
    "mystery": "dark suspense",
    "history": "cinematic orchestral",
}


async def download_bg_music(genre: str = "general") -> bytes | None:
    """Search Pixabay Music by genre and download the best matching track.

    Returns:
        MP3 bytes, or None if PIXABAY_API_KEY is not set / no track found.
    """
    key = _cfg("PIXABAY_API_KEY")
    if not key:
        logger.warning(
            "[bg_music] PIXABAY_API_KEY not set — skipping background music.\n"
            "  Get a free key at https://pixabay.com/api/docs/ and add it to Settings"
        )
        return None

    query = GENRE_QUERIES.get(genre.lower(), GENRE_QUERIES["general"])
    logger.info(f"[bg_music] Searching Pixabay Music: genre={genre!r} query={query!r}")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            _API_URL,
            params={
                "key": key,
                "q": query,
                "per_page": 5,
                "min_duration": 60,   # at least 1 minute so it covers most videos
            },
        )
        if not resp.is_success:
            logger.warning(f"[bg_music] Pixabay API error {resp.status_code}: {resp.text[:200]}")
            return None
        data = resp.json()

    hits = data.get("hits", [])
    if not hits:
        logger.warning(f"[bg_music] No tracks found for query '{query}'")
        return None

    track = hits[0]
    audio_url: str = track.get("audio", "")
    if not audio_url:
        logger.warning("[bg_music] Track has no audio URL")
        return None

    title = track.get("title", "unknown")
    artist = track.get("user", "unknown")
    duration = track.get("duration", 0)
    logger.info(f"[bg_music] Downloading: '{title}' by {artist} ({duration}s)")

    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        audio_resp = await client.get(audio_url)
        if not audio_resp.is_success:
            logger.warning(f"[bg_music] Audio download failed {audio_resp.status_code}")
            return None
        logger.info(f"[bg_music] Downloaded {len(audio_resp.content) / 1024:.0f} KB")
        return audio_resp.content
