"""Runtime settings store — overrides environment variables at runtime.

Values are persisted to a JSON file so they survive server restarts.
`get()` first checks the store, then falls back to os.getenv().

File location: AUTOVID_SETTINGS_PATH env var, or ~/.autovid-pro/settings.json
"""
import json
import logging
import os
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)

_LOCK = Lock()

# Keys that hold secret values and should be masked in API responses
SECRET_KEYS = {
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GOOGLE_AI_API_KEY",
    "STABLE_DIFFUSION_API_KEY",
    "ELEVENLABS_API_KEY",
    "RUNWAY_API_KEY",
    "PIXABAY_API_KEY",
    "YOUTUBE_API_KEY",
}

# Keys exposed through the settings API (in display order)
ALL_KEYS = [
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GOOGLE_AI_API_KEY",
    "STABLE_DIFFUSION_API_KEY",
    "ELEVENLABS_API_KEY",
    "ELEVENLABS_DEFAULT_VOICE_ID",
    "RUNWAY_API_KEY",
    "PIXABAY_API_KEY",
    "YOUTUBE_API_KEY",
    "IMAGE_PROVIDER",
]


def _store_path() -> Path:
    custom = os.getenv("AUTOVID_SETTINGS_PATH")
    if custom:
        return Path(custom)
    return Path.home() / ".autovid-pro" / "settings.json"


def _load() -> dict:
    path = _store_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(f"[settings_store] Failed to load {path}: {exc}")
        return {}


def _save_raw(data: dict) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get(key: str, default: str = "") -> str:
    """Return the value for *key*, preferring the file store over os.getenv."""
    with _LOCK:
        store = _load()
    val = store.get(key)
    if val is not None and str(val).strip():
        return str(val)
    return os.getenv(key, default)


def save(updates: dict) -> None:
    """Merge *updates* into the store and persist to disk."""
    with _LOCK:
        store = _load()
        for k, v in updates.items():
            if k in ALL_KEYS:
                # Empty string → remove override so os.getenv takes over
                if v is None or str(v).strip() == "":
                    store.pop(k, None)
                else:
                    store[k] = str(v).strip()
        _save_raw(store)


def get_all_masked() -> dict:
    """Return all managed keys with secret values masked for display.

    Non-secret keys (IMAGE_PROVIDER, ELEVENLABS_DEFAULT_VOICE_ID) are returned as-is.
    Secret keys show only the last 4 characters: '••••••••abcd'.
    Empty/unset values are returned as ''.
    """
    result = {}
    for key in ALL_KEYS:
        raw = get(key)
        if not raw:
            result[key] = ""
        elif key in SECRET_KEYS:
            if len(raw) <= 4:
                result[key] = "••••"
            else:
                result[key] = "••••••••" + raw[-4:]
        else:
            result[key] = raw
    return result
