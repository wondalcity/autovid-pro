"""YouTube Data API v3 utilities.

OAuth2 setup
------------
YouTube uploads require user-level OAuth2 (service accounts are NOT supported).

One-time setup (run once per deployment):
  python setup_youtube_auth.py

This generates a token and prints the JSON to stdout.  Copy it into your .env:
  YOUTUBE_OAUTH_TOKEN_JSON={"token": "...", "refresh_token": "...", ...}

Env vars required for upload:
  YOUTUBE_CLIENT_SECRETS_JSON  — content of the OAuth2 client_secrets.json downloaded
                                  from Google Cloud Console (Desktop app type)
  YOUTUBE_OAUTH_TOKEN_JSON     — token JSON produced by setup_youtube_auth.py
"""
import asyncio
import io
import json
import logging
import os
import re
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
_YT_BASE = "https://www.googleapis.com/youtube/v3"


# ─── URL parsing ─────────────────────────────────────────────────────────────

def extract_video_id(url: str) -> Optional[str]:
    """Extract the 11-character video ID from any YouTube URL format."""
    pattern = r"(?:v=|/embed/|/shorts/|youtu\.be/)([a-zA-Z0-9_-]{11})"
    m = re.search(pattern, url)
    return m.group(1) if m else None


# ─── Video metadata + comments ───────────────────────────────────────────────

async def fetch_video_details(video_id: str) -> dict:
    """Fetch video metadata and top 20 comments via YouTube Data API v3.

    Returns a dict with:
        video_id, title, description, published_at,
        view_count, like_count, comment_count, top_comments (list[str])
    """
    if not YOUTUBE_API_KEY:
        logger.warning("[youtube_api] YOUTUBE_API_KEY not set — skipping metadata fetch")
        return {"video_id": video_id, "title": "", "top_comments": []}

    async with httpx.AsyncClient(timeout=20) as client:
        # --- Video snippet + statistics ---
        video_resp = await client.get(
            f"{_YT_BASE}/videos",
            params={
                "part": "snippet,statistics",
                "id": video_id,
                "key": YOUTUBE_API_KEY,
            },
        )
        video_resp.raise_for_status()
        items = video_resp.json().get("items", [])
        if not items:
            logger.warning(f"[youtube_api] No video found for id={video_id}")
            return {"video_id": video_id, "title": "", "top_comments": []}

        snippet = items[0]["snippet"]
        stats = items[0].get("statistics", {})
        details: dict = {
            "video_id": video_id,
            "title": snippet.get("title", ""),
            "description": (snippet.get("description") or "")[:500],
            "published_at": snippet.get("publishedAt", ""),
            "view_count": int(stats.get("viewCount") or 0),
            "like_count": int(stats.get("likeCount") or 0),
            "comment_count": int(stats.get("commentCount") or 0),
            "top_comments": [],
        }

        # --- Top comments (sorted by relevance) ---
        try:
            comments_resp = await client.get(
                f"{_YT_BASE}/commentThreads",
                params={
                    "part": "snippet",
                    "videoId": video_id,
                    "order": "relevance",
                    "maxResults": 20,
                    "key": YOUTUBE_API_KEY,
                },
            )
            comments_resp.raise_for_status()
            comment_items = comments_resp.json().get("items", [])
            details["top_comments"] = [
                item["snippet"]["topLevelComment"]["snippet"]["textOriginal"]
                for item in comment_items
            ]
        except httpx.HTTPStatusError as exc:
            # Comments may be disabled on the video — non-fatal
            logger.warning(
                f"[youtube_api] Comments unavailable for {video_id}: {exc.response.status_code}"
            )

    return details


# ─── Keyword search ───────────────────────────────────────────────────────────

async def search_videos(keyword: str, max_results: int = 5) -> list[str]:
    """Search YouTube for videos matching a keyword and return their URLs.

    Results are ordered by view count (most-viewed first) so the benchmarking
    agent analyses the most influential videos in that niche.

    Args:
        keyword:     Search query (Korean or English).
        max_results: Number of video URLs to return (default 5).

    Returns:
        List of ``https://www.youtube.com/watch?v=...`` URLs.
        Returns an empty list if YOUTUBE_API_KEY is not configured.
    """
    if not YOUTUBE_API_KEY or YOUTUBE_API_KEY.strip() in ("", "..."):
        logger.warning(
            "[youtube_api] YOUTUBE_API_KEY not set — cannot auto-search videos. "
            "Add YOUTUBE_API_KEY to your .env file."
        )
        return []

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            f"{_YT_BASE}/search",
            params={
                "part": "snippet",
                "q": keyword,
                "type": "video",
                "order": "viewCount",
                "maxResults": max_results,
                "relevanceLanguage": "ko",
                "key": YOUTUBE_API_KEY,
            },
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        urls = [
            f"https://www.youtube.com/watch?v={item['id']['videoId']}"
            for item in items
            if item.get("id", {}).get("videoId")
        ]
        logger.info(
            f"[youtube_api] search '{keyword}' → {len(urls)} video(s) found"
        )
        return urls


# ─── Transcript ───────────────────────────────────────────────────────────────

def _sync_fetch_transcript(video_id: str) -> str:
    """Synchronous transcript fetch — meant to run in a thread executor."""
    try:
        from youtube_transcript_api import (
            YouTubeTranscriptApi,
            NoTranscriptFound,
            TranscriptsDisabled,
        )
    except ImportError:
        logger.error("[youtube_api] youtube-transcript-api not installed")
        return ""

    # Try preferred languages in order, then fall back to any auto-generated
    for langs in [["ko"], ["en"], ["ko", "en"]]:
        try:
            segments = YouTubeTranscriptApi.get_transcript(video_id, languages=langs)
            return " ".join(seg["text"] for seg in segments)
        except Exception:
            continue

    # Last resort: use whichever transcript is available
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        for transcript in transcript_list:
            try:
                segments = transcript.fetch()
                return " ".join(seg["text"] for seg in segments)
            except Exception:
                continue
    except Exception as exc:
        logger.warning(f"[youtube_api] Transcript unavailable for {video_id}: {exc}")

    return ""


async def fetch_transcript(youtube_url: str) -> str:
    """Fetch subtitle/transcript text for a YouTube video URL.

    Tries Korean → English → any available language.
    Returns an empty string if no transcript is found.
    """
    video_id = extract_video_id(youtube_url)
    if not video_id:
        logger.warning(f"[youtube_api] Cannot parse video ID from: {youtube_url}")
        return ""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_fetch_transcript, video_id)


# ─── OAuth2 helpers ───────────────────────────────────────────────────────────

_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]


def _load_credentials(token_json: str):
    """Build google.oauth2.credentials.Credentials from a stored token JSON string."""
    from google.oauth2.credentials import Credentials

    token_data: dict = json.loads(token_json)
    client_secrets_json: str = os.getenv("YOUTUBE_CLIENT_SECRETS_JSON", "")
    client_data: dict = {}
    if client_secrets_json:
        raw = json.loads(client_secrets_json)
        # client_secrets.json has a top-level key "installed" or "web"
        client_data = raw.get("installed") or raw.get("web") or {}

    return Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token_data.get("client_id") or client_data.get("client_id", ""),
        client_secret=token_data.get("client_secret") or client_data.get("client_secret", ""),
        scopes=token_data.get("scopes") or _SCOPES,
    )


def _build_youtube_service(token_json: str):
    """Build an authenticated YouTube Data API v3 service resource."""
    import google.auth.transport.requests as google_requests
    from googleapiclient.discovery import build

    creds = _load_credentials(token_json)
    # Refresh the access token if it has expired
    if not creds.valid:
        request = google_requests.Request()
        creds.refresh(request)
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def get_oauth_auth_url(redirect_uri: str) -> str:
    """Generate the Google OAuth2 authorization URL.

    The user visits this URL, grants access, and is redirected to
    `redirect_uri?code=...&state=...`.

    Requires YOUTUBE_CLIENT_SECRETS_JSON env var.
    Returns the authorization URL string.
    """
    from google_auth_oauthlib.flow import Flow

    client_secrets_json = os.getenv("YOUTUBE_CLIENT_SECRETS_JSON", "")
    if not client_secrets_json:
        raise RuntimeError("YOUTUBE_CLIENT_SECRETS_JSON env var not set")

    client_config = json.loads(client_secrets_json)
    flow = Flow.from_client_config(
        client_config,
        scopes=_SCOPES,
        redirect_uri=redirect_uri,
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",           # always prompt → always returns refresh_token
    )
    return auth_url


def exchange_oauth_code(code: str, redirect_uri: str) -> str:
    """Exchange an OAuth2 authorization code for a token JSON string.

    Returns:
        JSON string containing token, refresh_token, client_id, client_secret,
        token_uri, and scopes — suitable for storing as YOUTUBE_OAUTH_TOKEN_JSON.
    """
    from google_auth_oauthlib.flow import Flow

    client_secrets_json = os.getenv("YOUTUBE_CLIENT_SECRETS_JSON", "")
    if not client_secrets_json:
        raise RuntimeError("YOUTUBE_CLIENT_SECRETS_JSON env var not set")

    client_config = json.loads(client_secrets_json)
    client_data = (
        client_config.get("installed") or client_config.get("web") or {}
    )
    flow = Flow.from_client_config(
        client_config,
        scopes=_SCOPES,
        redirect_uri=redirect_uri,
    )
    flow.fetch_token(code=code)
    creds = flow.credentials
    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id or client_data.get("client_id", ""),
        "client_secret": creds.client_secret or client_data.get("client_secret", ""),
        "scopes": list(creds.scopes or _SCOPES),
    }
    return json.dumps(token_data)


# ─── Upload helpers ───────────────────────────────────────────────────────────

def _sync_upload_video(
    video_bytes: bytes,
    title: str,
    description: str,
    tags: list[str],
    category_id: str,
    privacy_status: str,
    token_json: str,
) -> str:
    """Blocking YouTube video upload via resumable upload.

    Returns the YouTube video ID string on success.
    """
    from googleapiclient.http import MediaIoBaseUpload

    youtube = _build_youtube_service(token_json)

    body = {
        "snippet": {
            "title": title[:100],                   # YouTube title limit: 100 chars
            "description": description[:5000],      # description limit: 5000 chars
            "tags": tags[:500],                     # tag list limit
            "categoryId": category_id,              # "22" = People & Blogs
            "defaultLanguage": "ko",
        },
        "status": {
            "privacyStatus": privacy_status,        # "private" | "unlisted" | "public"
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaIoBaseUpload(
        io.BytesIO(video_bytes),
        mimetype="video/mp4",
        chunksize=10 * 1024 * 1024,   # 10 MB chunks
        resumable=True,
    )

    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            logger.info(f"[youtube_api] Upload progress: {pct}%")

    video_id: str = response["id"]
    logger.info(f"[youtube_api] Video uploaded — id={video_id}")
    return video_id


def _sync_set_thumbnail(
    video_id: str,
    thumbnail_bytes: bytes,
    token_json: str,
) -> None:
    """Set the custom thumbnail for a YouTube video (blocking)."""
    from googleapiclient.http import MediaIoBaseUpload

    youtube = _build_youtube_service(token_json)
    media = MediaIoBaseUpload(
        io.BytesIO(thumbnail_bytes),
        mimetype="image/png",
        resumable=False,
    )
    youtube.thumbnails().set(
        videoId=video_id,
        media_body=media,
    ).execute()
    logger.info(f"[youtube_api] Thumbnail set for video {video_id}")


async def upload_video_bytes(
    video_bytes: bytes,
    title: str,
    description: str,
    tags: list[str],
    token_json: str,
    category_id: str = "22",
    privacy_status: str = "private",
) -> str:
    """Upload video bytes to YouTube and return the video ID.

    Runs the blocking Google API call in a thread so the event loop stays free.

    Args:
        video_bytes:    Raw MP4 bytes.
        title:          YouTube video title (≤ 100 chars).
        description:    Video description (≤ 5 000 chars).
        tags:           List of keyword tags.
        token_json:     OAuth2 token JSON string (YOUTUBE_OAUTH_TOKEN_JSON).
        category_id:    YouTube category ID (default "22" = People & Blogs).
        privacy_status: "private" | "unlisted" | "public" (default "private").

    Returns:
        YouTube video ID string (11 chars).
    """
    return await asyncio.to_thread(
        _sync_upload_video,
        video_bytes, title, description, tags,
        category_id, privacy_status, token_json,
    )


async def set_thumbnail(
    video_id: str,
    thumbnail_bytes: bytes,
    token_json: str,
) -> None:
    """Set a custom thumbnail on a YouTube video (non-blocking wrapper)."""
    await asyncio.to_thread(_sync_set_thumbnail, video_id, thumbnail_bytes, token_json)
