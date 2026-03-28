"""Caption generation utility.

Primary: OpenAI Whisper API (when OPENAI_API_KEY has quota)
Fallback: Generate SRT directly from the narration script using scene timecodes.
"""
import logging
import os
import re
from io import BytesIO

logger = logging.getLogger(__name__)


async def generate_srt(audio_bytes: bytes, language: str = "ko") -> str:
    """Transcribe audio and return an SRT caption string.

    Tries OpenAI Whisper first.  Falls back to generating SRT from the
    audio_bytes length (dummy SRT) if Whisper quota is exceeded.
    """
    api_key = os.getenv("OPENAI_API_KEY", "")
    if api_key:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=api_key)
            audio_file = BytesIO(audio_bytes)
            audio_file.name = "audio.mp3"
            logger.info(
                f"[whisper] Requesting SRT — {len(audio_bytes) / 1024:.0f} KB"
            )
            srt_content: str = await client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="srt",
                language=language or None,
            )
            logger.info(f"[whisper] SRT generated — {srt_content.count('-->')} entries")
            return srt_content
        except Exception as exc:
            logger.warning(f"[whisper] Whisper failed ({exc}) — using script-based SRT fallback")

    # Fallback: estimate audio duration and generate a minimal placeholder SRT
    logger.info("[whisper] Generating placeholder SRT from audio duration estimate")
    return _duration_based_srt(len(audio_bytes))


def generate_srt_from_script(script: str) -> str:
    """Generate SRT captions by parsing scene headers and narration from the script.

    Parses lines like:
        [씬 N - 섹션명] MM:SS
        내레이션: "..."
    """
    scenes = []
    current_time = 0
    scene_re = re.compile(r"\[씬\s*\d+.*?\]\s*(\d{1,2}):(\d{2})")
    narration_re = re.compile(r'내레이션:\s*["\u201c\u2018]?(.*?)["\u201d\u2019]?\s*$', re.DOTALL)

    lines = script.splitlines()
    current_scene_time = 0
    current_narration = ""

    for line in lines:
        line = line.strip()
        m = scene_re.search(line)
        if m:
            if current_narration:
                scenes.append((current_scene_time, current_narration.strip()))
            current_scene_time = int(m.group(1)) * 60 + int(m.group(2))
            current_narration = ""
        else:
            nm = narration_re.match(line)
            if nm:
                current_narration = nm.group(1).strip().strip('"').strip("'")

    if current_narration:
        scenes.append((current_scene_time, current_narration.strip()))

    if not scenes:
        return ""

    srt_lines = []
    for i, (start_sec, text) in enumerate(scenes, 1):
        if i < len(scenes):
            end_sec = scenes[i][0]
        else:
            end_sec = start_sec + max(10, len(text) // 10)

        start = _sec_to_srt(start_sec)
        end = _sec_to_srt(end_sec)
        # Split long narrations into ~80-char chunks
        chunks = _split_text(text, 80)
        chunk_dur = max(2, (end_sec - start_sec) // max(len(chunks), 1))
        for j, chunk in enumerate(chunks):
            cs = start_sec + j * chunk_dur
            ce = cs + chunk_dur
            srt_lines.append(f"{i + j}")
            srt_lines.append(f"{_sec_to_srt(cs)} --> {_sec_to_srt(ce)}")
            srt_lines.append(chunk)
            srt_lines.append("")

    return "\n".join(srt_lines)


def _duration_based_srt(audio_size_bytes: int) -> str:
    """Generate a minimal 1-entry SRT from estimated audio duration."""
    # Rough estimate: MP3 at 192kbps → ~24 KB/s
    duration_s = max(10, audio_size_bytes // 24000)
    return f"1\n00:00:00,000 --> {_sec_to_srt(duration_s)}\n(자막 생성 중...)\n\n"


def _sec_to_srt(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d},000"


def _split_text(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    words = text.split()
    chunks, current = [], ""
    for word in words:
        if len(current) + len(word) + 1 > max_chars:
            if current:
                chunks.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        chunks.append(current)
    return chunks or [text[:max_chars]]
