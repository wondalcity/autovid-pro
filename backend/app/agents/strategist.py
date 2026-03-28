"""Strategist Agent — competitive analysis of YouTube videos for content strategy."""
import json
import logging

from app.utils.llm import chat_json

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a senior YouTube content strategist specializing in competitive analysis.

Given data from one or more benchmark YouTube videos (titles, stats, top comments, transcripts),
produce a comprehensive JSON analysis with EXACTLY these top-level keys:

1. "title_thumbnail_patterns"
   - "patterns": list of observed title construction patterns
     (e.g., "숫자 리스트형", "How-to형", "의문문형", "충격 사실형")
   - "hook_words": list of power words / emotional triggers found in titles
   - "thumbnail_style": short description of the visual style inferred from titles/context

2. "story_structure"
   - "intro_style": how videos typically open (e.g., "강한 질문으로 시작", "충격 통계 제시")
   - "main_body_format": content organization pattern (e.g., "3단계 설명", "Q&A 구조")
   - "conclusion_style": how videos close (e.g., "CTA 강조", "요약 + 구독 유도")
   - "pacing": overall pacing notes

3. "key_facts": list of the most important facts and information extracted across all transcripts
   (minimum 5 items, each a concise statement)

4. "comment_insights"
   - "hot_points": list of topics / moments that generated the most viewer engagement
   - "common_questions": list of recurring viewer questions or confusions
   - "overall_sentiment": one of "positive" | "mixed" | "negative"
   - "emotional_triggers": list of emotional topics that resonated (e.g., "경제 불안", "성공 욕구")

5. "suggested_angles": list of 3–5 content angle ideas for a new video based on this research

6. "target_audience": paragraph describing the ideal viewer profile
   (demographics, interests, pain points, motivation to watch)

7. "competitive_summary": 2–3 sentence overall strategic takeaway

Return ONLY valid JSON. No markdown fences, no extra text."""


class StrategistAgent:
    async def analyze(self, video_data: list[dict]) -> dict:
        """Analyze one or more YouTube videos and return structured content strategy."""
        if not video_data:
            return {}

        videos_payload = []
        for vd in video_data:
            details = vd.get("details") or {}
            transcript = (vd.get("transcript") or "").strip()
            videos_payload.append({
                "url": vd.get("url", ""),
                "title": details.get("title", ""),
                "view_count": details.get("view_count", 0),
                "like_count": details.get("like_count", 0),
                "comment_count": details.get("comment_count", 0),
                "transcript_excerpt": transcript[:3000] if transcript else "(unavailable)",
                "top_comments": (details.get("top_comments") or [])[:10],
            })

        user_message = (
            f"Analyze the following {len(videos_payload)} YouTube video(s) "
            f"for competitive benchmarking:\n\n"
            f"{json.dumps(videos_payload, ensure_ascii=False, indent=2)}\n\n"
            "Return only valid JSON as described."
        )

        try:
            return await chat_json(_SYSTEM_PROMPT, user_message, temperature=0.3)
        except Exception as exc:
            logger.error(f"[StrategistAgent.analyze] LLM call failed: {exc}")
            return {}

    async def generate_youtube_meta(
        self, final_script: str, planning_doc: dict
    ) -> dict:
        """Generate YouTube upload metadata (title, description, tags) from the final script."""
        system_prompt = """You are an expert YouTube SEO specialist.

Given a final video script and the content planning document, produce upload-ready
YouTube metadata as EXACTLY this JSON object:

{
  "title": "<compelling Korean video title, ≤ 60 chars, high CTR>",
  "description": "<full Korean YouTube description, 200-400 chars, with 2-3 keyword phrases naturally embedded>",
  "tags": ["tag1", "tag2", ..., "tag15"]
}

Rules:
- title: Use numbers, power words, or questions proven to drive clicks.
- description: Open with the core value prop. Include a call-to-action (like/subscribe).
- tags: Mix broad (genre) + specific (topic) + branded ("AutoVidPro") tags.
- Return ONLY valid JSON. No markdown, no extra text."""

        ctr = (planning_doc or {}).get("ctr_design", {})
        concept = (planning_doc or {}).get("story_concept", {})
        user_message = (
            f"Planning doc summary:\n"
            f"  Main theme: {concept.get('main_theme', '')}\n"
            f"  Title candidates: {ctr.get('title_candidates', [])}\n\n"
            f"Final script (first 3000 chars):\n{final_script[:3000]}\n\n"
            "Generate the YouTube metadata JSON."
        )

        try:
            result = await chat_json(system_prompt, user_message, temperature=0.4)
            return {
                "title": result.get("title", ""),
                "description": result.get("description", ""),
                "tags": result.get("tags", []),
            }
        except Exception as exc:
            logger.error(f"[StrategistAgent.generate_youtube_meta] LLM call failed: {exc}")
            return {"title": "", "description": "", "tags": []}

    async def generate_thumbnail_prompt(
        self,
        youtube_title: str,
        analysis_result: dict,
    ) -> dict:
        """Generate a high-CTR thumbnail image prompt."""
        system_prompt = """You are a YouTube thumbnail design expert specializing in high click-through-rate visuals.

Given a YouTube video title and competitive benchmarking data, produce a thumbnail specification as EXACTLY this JSON:

{
  "prompt": "<Stable Diffusion English prompt — photorealistic or cinematic style, vivid colors, dramatic lighting, NO text in image, 16:9, high detail. Describe subject, background, mood, color palette, camera angle>",
  "overlay_text": "<Short Korean text ≤ 10 chars that will be overlaid on the thumbnail — a punchy hook word or number, e.g. '연봉 2억?' or '3가지 비밀'>",
  "style_notes": "<1-2 sentences explaining why this design will drive clicks>"
}

Thumbnail design rules:
- Use bold, contrasting colors (deep blue/red + bright yellow, or dark background + neon accent).
- Show one clear hero subject (person, object, graph) that represents the video's core hook.
- Leave space on one side for text overlay — the image should not look crowded.
- Convey emotion: curiosity, surprise, or aspiration.
- NO text, numbers, or letters in the generated image prompt itself — overlay_text handles that separately.
- Return ONLY valid JSON. No markdown, no extra text."""

        patterns = (analysis_result.get("title_thumbnail_patterns") or {})
        hook_words = patterns.get("hook_words", [])[:5]
        thumb_style = patterns.get("thumbnail_style", "")
        audience = analysis_result.get("target_audience", "")[:200]
        angles = (analysis_result.get("suggested_angles") or [])[:3]

        user_message = (
            f"Video title: {youtube_title}\n\n"
            f"Competitor thumbnail style: {thumb_style}\n"
            f"Emotional hook words used by competitors: {hook_words}\n"
            f"Target audience: {audience}\n"
            f"Content angles: {angles}\n\n"
            "Generate the thumbnail specification JSON."
        )

        try:
            result = await chat_json(system_prompt, user_message, temperature=0.6)
            return {
                "prompt": result.get("prompt", ""),
                "overlay_text": result.get("overlay_text", ""),
                "style_notes": result.get("style_notes", ""),
            }
        except Exception as exc:
            logger.error(
                f"[StrategistAgent.generate_thumbnail_prompt] LLM call failed: {exc}"
            )
            return {
                "prompt": (
                    "YouTube thumbnail, dramatic lighting, vivid colors, "
                    "cinematic, high contrast, 16:9, professional photography"
                ),
                "overlay_text": "",
                "style_notes": "",
            }
