"""PD Agent — generates planning documents, scripts, and storyboards."""
import json
import logging

from app.utils.llm import chat_json, chat_text

logger = logging.getLogger(__name__)


# ─── System prompts ───────────────────────────────────────────────────────────

_PLANNING_DOC_SYSTEM = """You are a senior YouTube content producer and creative director.

Given a competitive benchmarking analysis and an optional story concept from the creator,
write a comprehensive content planning document (기획서) in Korean.

Return a JSON object with EXACTLY these top-level keys:

1. "story_concept"
   - "main_theme": core theme of the video (str)
   - "narrative_angle": unique angle that differentiates this video (str)
   - "unique_value_proposition": what the viewer gains that they cannot get elsewhere (str)

2. "ctr_design"
   - "title_candidates": list of 4-5 compelling title options (list of str, Korean)
   - "thumbnail_concept": visual concept description for the thumbnail (str)
   - "a_b_test_ideas": list of 2-3 alternative title/thumbnail approaches (list of str)

3. "hook_intro_strategy"
   - "opening_hook": exact first sentence/question that grabs attention (str, Korean)
   - "problem_statement": the viewer's pain point or curiosity this video addresses (str)
   - "promise_to_viewer": what the viewer will learn/get by watching (str)
   - "intro_script_draft": a full 30-60 second intro script draft (str, Korean)

4. "content_outline": ordered list of sections, each with:
   - "section_name": name of the section (str, Korean)
   - "timecode": estimated timecode range e.g. "0:00-1:30" (str)
   - "key_points": list of 2-4 main points to cover (list of str)
   - "transition_cue": how to transition to the next section (str)

5. "target_tone": overall tone and style e.g. "전문적이고 신뢰감 있는" (str)
6. "estimated_duration": estimated total video length e.g. "10-15분" (str)

Return ONLY valid JSON. No markdown, no extra text."""

_SCRIPT_SYSTEM = """You are an expert YouTube scriptwriter. Write in natural, conversational Korean.

Based on the provided planning document (기획서), write a complete broadcast-ready video script.

Formatting rules (CRITICAL — follow exactly):
- Each scene starts with a header line: [씬 N - 섹션명] HH:MM
- After the header, write: 내레이션: "..." (the exact words spoken by the host)
- After narration, write: 화면: ... (B-roll, visual direction, on-screen text)
- Leave one blank line between scenes
- Do NOT use markdown headers, JSON, or bullet points in the script body
- Write naturally — the way a real person speaks, not bullet points

Example format:
[씬 1 - 인트로] 00:00
내레이션: "여러분, 혹시 이런 경험 있으신가요? 월급은 받았는데..."
화면: 직장인이 통장 잔액을 보며 한숨 쉬는 장면 / 은행 앱 화면 클로즈업

[씬 2 - 문제 제기] 01:00
내레이션: "오늘은 이 문제를 해결해 드릴게요. 제가 직접 해본 방법입니다."
화면: 그래프 애니메이션, 전문가 인터뷰 B-roll

Return ONLY the plain text script. Start with [씬 1 - 인트로]."""


class PdAgent:
    # ─── Stage 1: planning document ──────────────────────────────────────────

    async def write_planning_doc(
        self, analysis_result: dict, story_concept: str = ""
    ) -> dict:
        """Generate a structured content planning document (기획서)."""
        user_message = (
            "Benchmarking Analysis:\n"
            f"{json.dumps(analysis_result, ensure_ascii=False, indent=2)}\n\n"
            f"Creator's Story Concept: {story_concept or '(none provided — use your best judgement)'}\n\n"
            "Write the content planning document as JSON."
        )
        try:
            return await chat_json(_PLANNING_DOC_SYSTEM, user_message, temperature=0.5)
        except Exception as exc:
            logger.error(f"[PdAgent.write_planning_doc] Error: {exc}")
            return {}

    # ─── Stage 2: scene-based script with timecodes ──────────────────────────

    async def write_script_from_planning(self, planning_doc: dict) -> str:
        """Write a full scene-based video script from a planning document."""
        user_message = (
            "Planning Document (기획서):\n"
            f"{json.dumps(planning_doc, ensure_ascii=False, indent=2)}\n\n"
            "Write the complete video script following the format rules exactly."
        )
        try:
            return await chat_text(_SCRIPT_SYSTEM, user_message, temperature=0.6, max_tokens=8192)
        except Exception as exc:
            logger.error(f"[PdAgent.write_script_from_planning] Error: {exc}")
            return ""

    # ─── Stage 4: storyboard (used by step_runner step 4) ────────────────────

    async def create_storyboard(self, script: str) -> list[dict]:
        """Break a video script into visual scenes for storyboarding."""
        system_prompt = (
            "You are an expert YouTube video storyboard creator.\n\n"
            "Given a scene-formatted video script, break it into distinct visual scenes.\n\n"
            "Return a JSON object with a single key \"scenes\" whose value is a list.\n"
            "Each scene object must have EXACTLY these keys:\n\n"
            "- \"scene_id\": string in zero-padded format: \"scene_01\", \"scene_02\", etc.\n"
            "- \"timestamp\": estimated time range, e.g. \"00:00 - 00:15\"\n"
            "- \"description\": Korean, 1-2 sentences describing what happens visually\n"
            "- \"narration\": the narration text spoken in this scene (Korean)\n"
            "- \"image_prompt\": detailed English prompt for AI image generation.\n"
            "  Must include: shot type (wide/medium/close-up), lighting, mood, art style.\n"
            "  Example: \"Wide cinematic shot of Seoul skyline at night, neon reflections "
            "on wet pavement, dramatic low-angle, photorealistic, 8K\"\n"
            "- \"video_prompt\": camera movement instructions for a video AI agent.\n"
            "  Example: \"slow pan right\", \"zoom in gradually\", \"static wide shot\"\n\n"
            "Return ONLY valid JSON with the key \"scenes\". No markdown, no extra text."
        )
        user_message = (
            f"Script:\n{script}\n\n"
            "Create a storyboard with ONE scene per script section. "
            "Limit to a MAXIMUM of 8 scenes total. "
            "Keep image_prompt under 100 words each. "
            "Return only valid JSON with the key 'scenes'."
        )
        try:
            data = await chat_json(system_prompt, user_message, temperature=0.4, max_tokens=8192)
            scenes = data.get("scenes", [])
            return scenes[:12]  # cap at 12 scenes
        except Exception as exc:
            logger.error(f"[PdAgent.create_storyboard] Error: {exc}")
            return []
