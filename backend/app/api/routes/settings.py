"""API routes for runtime settings management.

GET  /settings        — returns all managed keys with masked secret values
POST /settings        — saves provided key/value pairs to the store
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.utils.settings_store import get_all_masked, save, ALL_KEYS

router = APIRouter()


class SettingsUpdate(BaseModel):
    # Accept any subset of the managed keys
    ANTHROPIC_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    GOOGLE_AI_API_KEY: str | None = None
    STABLE_DIFFUSION_API_KEY: str | None = None
    ELEVENLABS_API_KEY: str | None = None
    ELEVENLABS_DEFAULT_VOICE_ID: str | None = None
    RUNWAY_API_KEY: str | None = None
    PIXABAY_API_KEY: str | None = None
    YOUTUBE_API_KEY: str | None = None
    IMAGE_PROVIDER: str | None = None


@router.get("", summary="Get current settings (secrets masked)")
async def get_settings():
    """Return all managed settings. Secret keys are partially masked."""
    return {
        "settings": get_all_masked(),
        "managed_keys": ALL_KEYS,
    }


@router.post("", summary="Save settings")
async def update_settings(body: SettingsUpdate):
    """Save one or more settings to the runtime store.

    Passing an empty string for a key removes the override and falls back to the .env value.
    """
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    save(updates)
    return {
        "success": True,
        "settings": get_all_masked(),
    }
