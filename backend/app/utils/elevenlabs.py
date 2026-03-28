"""ElevenLabs TTS utility — single call and batch generation with audio merging.

System requirement: ffmpeg must be installed (required by pydub).
  macOS:  brew install ffmpeg
  Ubuntu: sudo apt install ffmpeg
"""
import logging
import os
import re
from io import BytesIO

import httpx

logger = logging.getLogger(__name__)

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
# Default voice: "Rachel" (multilingual, free tier available)
DEFAULT_VOICE_ID = os.getenv("ELEVENLABS_DEFAULT_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
_TTS_BASE = "https://api.elevenlabs.io/v1/text-to-speech"

# ElevenLabs text limit per request (characters)
_CHUNK_LIMIT = 4500


# ─── Text preprocessing ───────────────────────────────────────────────────────

def preprocess_text_for_tts(text: str) -> str:
    """Clean text before sending to TTS to improve speech quality.

    - Removes special characters that TTS engines may mispronounce or skip.
    - Preserves Korean/Latin alphanumerics, whitespace, and basic punctuation
      (,.?!\n) that help the model produce natural pauses and intonation.
    """
    text = re.sub(r'[^\w\s,.?!\n]', '', text)
    return text.strip()


# ─── Text chunking helpers ────────────────────────────────────────────────────

def split_into_chunks(text: str, limit: int = _CHUNK_LIMIT) -> list[str]:
    """Split text into chunks that fit within the ElevenLabs character limit.

    Splits on sentence boundaries (. ! ?) to preserve natural speech rhythm.
    """
    if len(text) <= limit:
        return [text]

    import re
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) + 1 > limit:
            if current:
                chunks.append(current.strip())
            current = sentence
        else:
            current = f"{current} {sentence}".strip() if current else sentence
    if current:
        chunks.append(current.strip())
    return chunks or [text[:limit]]


# ─── Single TTS call ─────────────────────────────────────────────────────────

async def _generate_tts_local(text: str) -> bytes:
    """Fallback TTS using macOS built-in 'say' command with Yuna (Korean) voice.

    Requires: macOS + ffmpeg installed.
    Returns MP3 bytes, or raises RuntimeError if not available.
    """
    import asyncio
    import tempfile
    import os as _os

    with tempfile.TemporaryDirectory() as tmpdir:
        aiff_path = _os.path.join(tmpdir, "tts.aiff")
        mp3_path = _os.path.join(tmpdir, "tts.mp3")

        # Use Yuna (Korean) voice; fall back to system default
        proc = await asyncio.create_subprocess_exec(
            "say", "-v", "Yuna", text, "-o", aiff_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        if proc.returncode != 0:
            # Try without specifying voice
            proc = await asyncio.create_subprocess_exec(
                "say", text, "-o", aiff_path,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
        if proc.returncode != 0:
            raise RuntimeError("macOS say command failed")

        # Convert AIFF → MP3 with ffmpeg
        proc2 = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", aiff_path, "-ar", "44100", "-ab", "192k", mp3_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc2.wait()
        if proc2.returncode != 0:
            raise RuntimeError("ffmpeg AIFF→MP3 conversion failed")

        with open(mp3_path, "rb") as f:
            return f.read()


async def generate_tts(text: str, voice_id: str = DEFAULT_VOICE_ID) -> bytes:
    """Generate speech for a single text string via ElevenLabs API.

    Args:
        text:     The narration text to synthesise (max ~4 500 chars).
        voice_id: ElevenLabs voice ID.

    Returns:
        MP3 audio bytes.

    Raises:
        RuntimeError: If ELEVENLABS_API_KEY is not set or the API call fails.
    """
    text = preprocess_text_for_tts(text)

    if ELEVENLABS_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{_TTS_BASE}/{voice_id}",
                    headers={
                        "xi-api-key": ELEVENLABS_API_KEY,
                        "Content-Type": "application/json",
                        "Accept": "audio/mpeg",
                    },
                    json={
                        "text": text,
                        "model_id": "eleven_multilingual_v2",
                        "voice_settings": {
                            "stability": 0.45,
                            "similarity_boost": 0.75,
                            "style": 0.0,
                            "use_speaker_boost": True,
                        },
                    },
                )
                resp.raise_for_status()
                return resp.content
        except Exception as exc:
            logger.warning(f"[elevenlabs] API call failed ({exc}) — falling back to local TTS")

    # Fallback: macOS built-in TTS
    try:
        return await _generate_tts_local(text)
    except Exception as exc:
        raise RuntimeError(f"All TTS methods failed. Last error: {exc}") from exc


# ─── Batch TTS + audio merge ─────────────────────────────────────────────────

async def generate_tts_batch(
    segments: list[str],
    voice_id: str = DEFAULT_VOICE_ID,
    pause_ms: int = 400,
) -> bytes:
    """Generate TTS for each segment, then merge into one MP3.

    Large segments are automatically chunked to stay within ElevenLabs limits.
    A short silence (`pause_ms` milliseconds) is inserted between segments for
    natural pacing.

    Args:
        segments:  List of narration strings (one per scene/paragraph).
        voice_id:  ElevenLabs voice ID.
        pause_ms:  Silence duration to insert between segments (ms).

    Returns:
        Merged MP3 audio as bytes.
    """
    from pydub import AudioSegment  # imported here to keep it optional at module level

    silence = AudioSegment.silent(duration=pause_ms)
    merged = AudioSegment.empty()
    total_segments = 0

    for i, segment in enumerate(segments):
        if not segment.strip():
            continue

        # Each segment may itself need to be chunked
        chunks = split_into_chunks(segment)
        for j, chunk in enumerate(chunks):
            logger.info(
                f"[elevenlabs] TTS segment {i + 1}/{len(segments)}"
                + (f" chunk {j + 1}/{len(chunks)}" if len(chunks) > 1 else "")
            )
            try:
                audio_bytes = await generate_tts(chunk, voice_id=voice_id)
                seg_audio = AudioSegment.from_mp3(BytesIO(audio_bytes))
                merged += seg_audio
                total_segments += 1
            except Exception as exc:
                logger.error(
                    f"[elevenlabs] TTS failed for segment {i + 1} chunk {j + 1}: {exc}"
                )
                # Insert silence placeholder so timing stays roughly intact
                merged += AudioSegment.silent(duration=2000)

        # Add pause between segments (not after the last one)
        if i < len(segments) - 1:
            merged += silence

    if len(merged) == 0:
        raise RuntimeError("Audio merge produced an empty result — all TTS calls failed")

    logger.info(
        f"[elevenlabs] Merged {total_segments} audio chunk(s) → "
        f"{len(merged) / 1000:.1f}s total"
    )
    output = BytesIO()
    merged.export(output, format="mp3", bitrate="192k")
    return output.getvalue()
