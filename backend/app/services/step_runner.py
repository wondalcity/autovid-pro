"""Step runner service — dispatches pipeline steps for a project."""
import asyncio
import json
import logging
import re
from datetime import datetime, timezone

from app.database import get_db
from app.agents.strategist import StrategistAgent
from app.agents.pd_agent import PdAgent
from app.utils import elevenlabs, stable_diffusion, youtube_api

logger = logging.getLogger(__name__)


# Global cancellation flags  {f"{project_id}:{step_num}": True}
_CANCEL_FLAGS: dict[str, bool] = {}

# Steps that pause for user review before advancing to next step
STEPS_NEEDING_REVIEW: set[int] = {2}


def request_cancel(project_id: str, step_num: int) -> None:
    """Signal that a running step should be cancelled."""
    _CANCEL_FLAGS[f"{project_id}:{step_num}"] = True


def _check_cancel(project_id: str, step_num: int) -> None:
    """Raise CancelledError if this step has been flagged for cancellation."""
    if _CANCEL_FLAGS.pop(f"{project_id}:{step_num}", False):
        raise asyncio.CancelledError(f"Step {step_num} cancelled by user")


def _upsert_step_log(
    db,
    project_id: str,
    step_num: int,
    status: str,
    message: str | None = None,
    progress: int | None = None,
) -> None:
    """Upsert a step_logs row for the given project/step."""
    now = datetime.now(timezone.utc).isoformat()
    data: dict = {
        "project_id": project_id,
        "step_num": step_num,
        "status": status,
        "message": message,
    }
    if progress is not None:
        data["progress"] = progress
    if status == "running":
        data["started_at"] = now
    elif status in ("done", "error", "awaiting_review"):
        data["finished_at"] = now
    try:
        db.table("step_logs").upsert(data, on_conflict="project_id,step_num").execute()
    except Exception as exc:
        logger.error(f"[_upsert_step_log] Failed for project {project_id} step {step_num}: {exc}")


def _update_progress(
    db, project_id: str, step_num: int, progress: int, message: str
) -> None:
    """Update progress percentage (0-100) and status message for a running step."""
    _upsert_step_log(db, project_id, step_num, "running", message, progress)


async def run_step(project_id: str, step_num: int, payload: dict) -> None:
    """Update current_step in DB and dispatch to the appropriate step handler."""
    db = get_db()
    try:
        db.table("projects").update({"current_step": step_num}).eq("id", project_id).execute()
    except Exception as e:
        logger.error(f"[run_step] Failed to update current_step for project {project_id}: {e}")

    _upsert_step_log(db, project_id, step_num, "running", "시작 중...", 0)

    handlers = {
        1: _step1_benchmarking,
        2: _step2_script,
        3: _step3_voice_subtitles,
        4: _step4_storyboard,
        5: _step5_images_video,
        6: _step6_editing,
        7: _step7_thumbnail,
        8: _step8_export_upload,
    }
    handler = handlers.get(step_num)
    if handler is None:
        logger.error(f"[run_step] Unknown step_num {step_num} for project {project_id}")
        _upsert_step_log(db, project_id, step_num, "error", f"Unknown step {step_num}")
        return

    try:
        await handler(project_id, payload)
        # Steps needing review manage their own final status (awaiting_review)
        if step_num not in STEPS_NEEDING_REVIEW:
            _upsert_step_log(db, project_id, step_num, "done", "완료", 100)
            db.table("projects").update({"current_step": step_num + 1}).eq("id", project_id).execute()
    except asyncio.CancelledError:
        logger.info(f"[run_step] Step {step_num} cancelled for project {project_id}")
        _upsert_step_log(db, project_id, step_num, "pending", "사용자에 의해 취소됨", 0)
        db.table("projects").update({"current_step": step_num}).eq("id", project_id).execute()
    except Exception as e:
        logger.error(f"[run_step] Step {step_num} failed for project {project_id}: {e}")
        _upsert_step_log(db, project_id, step_num, "error", str(e))


# ---------------------------------------------------------------------------
# Step handlers
# ---------------------------------------------------------------------------

async def _step1_benchmarking(project_id: str, payload: dict) -> None:
    """Fetch YouTube video details + transcripts for each URL, then run Strategist analysis.

    Payload keys:
        youtube_urls (list[str]): one or more YouTube URLs to benchmark.
        youtube_url  (str):       single URL fallback if youtube_urls is absent.

    For each URL a benchmarking row is inserted with raw data.
    After all URLs are processed the Strategist produces a combined analysis that
    is stored in analysis_result on the last inserted row.
    """
    db = get_db()

    # Normalise: accept list, newline-separated string, or single-URL field
    _raw = payload.get("youtube_urls") or []
    if isinstance(_raw, str):
        youtube_urls: list[str] = [u.strip() for u in _raw.splitlines() if u.strip()]
    else:
        youtube_urls = [str(u).strip() for u in _raw if str(u).strip()]
    if not youtube_urls and payload.get("youtube_url"):
        youtube_urls = [payload["youtube_url"]]
    _update_progress(db, project_id, 1, 5, "URL 준비 중...")

    # ── Auto-search: find 5 top videos when no URLs are given ────────────────
    if not youtube_urls:
        keyword: str = (payload.get("keyword") or "").strip()

        # Fall back to project title if no keyword supplied
        if not keyword:
            proj_res = (
                db.table("projects")
                .select("title")
                .eq("id", project_id)
                .single()
                .execute()
            )
            keyword = (proj_res.data or {}).get("title", "")

        if not keyword:
            raise RuntimeError(
                "YouTube URL과 키워드가 모두 없습니다. "
                "URL 또는 keyword를 입력해주세요."
            )

        logger.info(
            f"[step1] No URLs provided — auto-searching YouTube for: '{keyword}'"
        )
        try:
            youtube_urls = await youtube_api.search_videos(keyword, max_results=5)
        except Exception as exc:
            logger.error(f"[step1] YouTube auto-search failed: {exc}")

        if not youtube_urls:
            raise RuntimeError(
                f"'{keyword}' 키워드로 YouTube 검색에 실패했습니다. "
                "YOUTUBE_API_KEY가 .env에 올바르게 설정되어 있는지 확인해주세요."
            )

        logger.info(
            f"[step1] Auto-search found {len(youtube_urls)} videos: "
            + ", ".join(youtube_urls)
        )
    _update_progress(db, project_id, 1, 15, f"자동 검색 완료 — {len(youtube_urls)}개 영상 발견")

    all_video_data: list[dict] = []
    last_bench_id: str | None = None

    # ── Phase 1: fetch raw data for ALL URLs concurrently ────────────────────
    _update_progress(db, project_id, 1, 15, f"{len(youtube_urls)}개 영상 동시 분석 중...")

    async def _fetch_one(url: str) -> dict | None:
        """Fetch details + transcript for one URL. Returns None on error."""
        try:
            video_id = youtube_api.extract_video_id(url)
            details, transcript = await asyncio.gather(
                youtube_api.fetch_video_details(video_id) if video_id else asyncio.sleep(0, result={}),
                youtube_api.fetch_transcript(url),
            )
            return {"url": url, "details": details, "transcript": transcript}
        except Exception as exc:
            logger.error(f"[step1] Failed to fetch {url}: {exc}")
            return None

    _check_cancel(project_id, 1)
    fetch_results = await asyncio.gather(*[_fetch_one(u) for u in youtube_urls])

    _update_progress(db, project_id, 1, 60, "영상 데이터 저장 중...")
    for item in fetch_results:
        if item is None:
            continue
        try:
            insert_result = (
                db.table("benchmarking")
                .insert(
                    {
                        "project_id": project_id,
                        "youtube_url": item["url"],
                        "title": item["details"].get("title", ""),
                        "transcript": item["transcript"],
                        "analysis_result": None,
                    }
                )
                .execute()
            )
            if insert_result.data:
                last_bench_id = insert_result.data[0]["id"]
            all_video_data.append(item)
            logger.info(f"[step1] Raw data stored for {item['url']} (project {project_id})")
        except Exception as exc:
            logger.error(f"[step1] DB insert failed for {item['url']}: {exc}")

    if not all_video_data:
        logger.error(f"[step1] No video data collected — aborting analysis for project {project_id}")
        return

    # ── Phase 2: Strategist combined analysis ────────────────────────────────
    try:
        agent = StrategistAgent()
        _update_progress(db, project_id, 1, 85, "AI 경쟁 분석 중...")
        _check_cancel(project_id, 1)
        analysis: dict = await agent.analyze(all_video_data)

        if last_bench_id and analysis:
            db.table("benchmarking").update(
                {"analysis_result": analysis}
            ).eq("id", last_bench_id).execute()
            _update_progress(db, project_id, 1, 98, "분석 결과 저장 중...")
            logger.info(
                f"[step1] Strategist analysis saved (bench_id={last_bench_id}, "
                f"project={project_id}, videos={len(all_video_data)})"
            )
    except Exception as exc:
        logger.error(f"[step1] Strategist analysis failed for project {project_id}: {exc}")


async def _step2_script(project_id: str, payload: dict) -> None:
    """Two-stage script generation: planning doc → scene-based raw script.

    Stage 1 — PdAgent writes a full content planning document (기획서) from the
              Strategist analysis and saves it to scripts.planning_doc.
    Stage 2 — PdAgent writes a scene-by-scene raw script from the planning doc
              and saves it to scripts.raw_script.
    final_script is initialised to raw_script; the user edits and approves it
    via POST /projects/{id}/steps/2/approve.
    """
    db = get_db()
    _update_progress(db, project_id, 2, 10, "벤치마킹 데이터 로드 중...")
    story_concept: str = payload.get("story_concept", "")

    # ── Fetch benchmarking analysis ───────────────────────────────────────────
    bench_result = (
        db.table("benchmarking")
        .select("analysis_result")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    analysis_raw = bench_result.data[0]["analysis_result"] if bench_result.data else {}
    analysis_result = (
        json.loads(analysis_raw) if isinstance(analysis_raw, str) else (analysis_raw or {})
    )
    if not analysis_result:
        logger.warning(
            f"[step2] No benchmarking analysis found for project {project_id} — "
            "proceeding with empty analysis"
        )

    agent = PdAgent()

    # ── Stage 1: planning document ────────────────────────────────────────────
    logger.info(f"[step2] Generating planning doc for project {project_id}")
    _update_progress(db, project_id, 2, 35, "기획서 작성 중...")
    _check_cancel(project_id, 2)
    planning_doc = await agent.write_planning_doc(analysis_result, story_concept)
    if not planning_doc:
        raise RuntimeError("PdAgent returned an empty planning document")

    # Extract flat fields from the planning doc for easy querying
    ctr = planning_doc.get("ctr_design", {})
    hook = planning_doc.get("hook_intro_strategy", {})
    concept = planning_doc.get("story_concept", {})

    # Insert scripts row immediately so partial progress is preserved
    insert_result = (
        db.table("scripts")
        .insert(
            {
                "project_id": project_id,
                "story_concept": (
                    story_concept or concept.get("main_theme", "")
                ),
                "planning_doc": planning_doc,
                # flat convenience fields (populated after stage 2)
                "hook_intro": None,
                "ctr_design_ideas": None,
                "raw_script": None,
                "final_script": None,
            }
        )
        .execute()
    )
    if not insert_result.data:
        raise RuntimeError("Failed to insert scripts row")
    script_id: str = insert_result.data[0]["id"]
    logger.info(f"[step2] Planning doc saved (script_id={script_id})")

    # ── Stage 2: scene-based raw script ──────────────────────────────────────
    logger.info(f"[step2] Generating raw script for project {project_id}")
    _update_progress(db, project_id, 2, 65, "대본 작성 중...")
    _check_cancel(project_id, 2)
    raw_script = await agent.write_script_from_planning(planning_doc)
    if not raw_script:
        raise RuntimeError("PdAgent returned an empty raw script")

    _update_progress(db, project_id, 2, 90, "대본 저장 중...")
    db.table("scripts").update(
        {
            "hook_intro": hook.get("opening_hook", ""),
            "ctr_design_ideas": json.dumps(ctr.get("title_candidates", [])),
            "raw_script": raw_script,
            # final_script starts as raw_script — user edits & approves it
            "final_script": raw_script,
        }
    ).eq("id", script_id).execute()
    logger.info(f"[step2] Raw script saved for project {project_id}")

    # Step 2 waits for user review — mark awaiting_review instead of done
    _upsert_step_log(db, project_id, 2, "awaiting_review", "대본이 준비되었습니다. 검토 후 승인해주세요.", 100)


def _extract_narration_segments(script: str) -> list[str]:
    """Extract narration text from a scene-formatted script.

    Primary path  — finds all  내레이션: "..."  markers and returns their text.
    Fallback path — if no markers are found, strips scene headers and visual
                    direction lines and returns the remaining text as one block.
    """
    matches = re.findall(r'내레이션:\s*"([^"]+)"', script, re.DOTALL)
    if matches:
        return [m.strip() for m in matches if m.strip()]

    # Fallback: strip structural lines, keep narration prose
    lines = []
    for line in script.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("[씬") or stripped.startswith("화면:"):
            continue
        lines.append(stripped)
    return [" ".join(lines)] if lines else [script.strip()]


async def _step3_voice_subtitles(project_id: str, payload: dict) -> None:
    """Voice + subtitle generation pipeline.

    Flow:
      1. Fetch scripts.final_script
      2. Extract narration segments (scene-by-scene)
      3. ElevenLabs TTS for each segment → merge into one MP3
      4. Upload merged MP3 to Supabase Storage
      5. Save Storage URL in assets (asset_type='voice')
      6. OpenAI Whisper → SRT caption string
      7. Upload .srt to Supabase Storage
      8. Save Storage URL in assets (asset_type='caption')
    """
    from app.utils import storage, whisper_util

    db = get_db()
    _update_progress(db, project_id, 3, 10, "대본 로드 중...")
    voice_id: str = (
        payload.get("voice_id")
        or elevenlabs.DEFAULT_VOICE_ID
    )

    # ── 1. Fetch final_script ────────────────────────────────────────────────
    script_result = (
        db.table("scripts")
        .select("final_script")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not script_result.data or not script_result.data[0].get("final_script"):
        raise RuntimeError(
            f"No approved final_script found for project {project_id}. "
            "Complete Step 2 (approve the script) before running Step 3."
        )
    final_script: str = script_result.data[0]["final_script"]

    # ── 2. Extract narration segments ────────────────────────────────────────
    segments = _extract_narration_segments(final_script)
    logger.info(
        f"[step3] {len(segments)} narration segment(s) extracted "
        f"(project {project_id})"
    )

    # ── 3. ElevenLabs TTS → merged MP3 ──────────────────────────────────────
    logger.info(f"[step3] Generating TTS with voice_id={voice_id}")
    _update_progress(db, project_id, 3, 25, "음성 합성 중...")
    _check_cancel(project_id, 3)
    merged_audio: bytes = await elevenlabs.generate_tts_batch(
        segments, voice_id=voice_id
    )
    logger.info(
        f"[step3] TTS done — {len(merged_audio) / 1024:.0f} KB "
        f"(project {project_id})"
    )

    # ── 4. Upload MP3 to Supabase Storage ────────────────────────────────────
    _update_progress(db, project_id, 3, 60, "음성 파일 업로드 중...")
    audio_url: str = storage.upload_file(
        project_id=project_id,
        filename="voice.mp3",
        data=merged_audio,
        content_type="audio/mpeg",
    )

    # ── 5. Save voice asset ──────────────────────────────────────────────────
    db.table("assets").insert(
        {
            "project_id": project_id,
            "asset_type": "voice",
            "file_path": audio_url,
            "metadata": {
                "voice_id": voice_id,
                "segments": len(segments),
                "size_bytes": len(merged_audio),
            },
        }
    ).execute()
    logger.info(f"[step3] Voice asset saved → {audio_url}")

    # ── 6. Whisper → SRT (falls back to script-based SRT if quota exceeded) ──
    logger.info(f"[step3] Generating SRT captions (project {project_id})")
    _update_progress(db, project_id, 3, 75, "자막 생성 중...")
    _check_cancel(project_id, 3)
    srt_content: str = await whisper_util.generate_srt(merged_audio, language="ko")
    # If Whisper produced only a placeholder, replace with script-derived SRT
    if srt_content.strip() == "" or "(자막 생성 중...)" in srt_content:
        srt_content = whisper_util.generate_srt_from_script(final_script) or srt_content

    # ── 7. Upload .srt to Supabase Storage ───────────────────────────────────
    srt_url: str = storage.upload_file(
        project_id=project_id,
        filename="captions.srt",
        data=srt_content.encode("utf-8"),
        content_type="text/plain; charset=utf-8",
    )

    # ── 8. Save caption asset ────────────────────────────────────────────────
    _update_progress(db, project_id, 3, 90, "자막 파일 업로드 중...")
    db.table("assets").insert(
        {
            "project_id": project_id,
            "asset_type": "caption",
            "file_path": srt_url,
            "metadata": {
                "format": "srt",
                "language": "ko",
                "entries": srt_content.count("\n-->"),
            },
        }
    ).execute()
    logger.info(f"[step3] Caption asset saved → {srt_url}")


def _scene_id_to_int(scene_id: str | int) -> int:
    """Convert "scene_01" or 1 to an integer for the assets.scene_id column."""
    if isinstance(scene_id, int):
        return scene_id
    digits = "".join(c for c in str(scene_id) if c.isdigit())
    return int(digits) if digits else 0


async def _step4_storyboard(project_id: str, payload: dict) -> None:
    """Generate storyboard from final_script and persist each scene to the assets table.

    Each scene becomes one row in assets (asset_type='storyboard') with the
    full scene JSON stored in the metadata column.  The complete scenes array is
    also written to scripts.planning_doc so Step 5 can read image/video prompts.

    Scene structure produced by PdAgent.create_storyboard():
        scene_id     (str)  "scene_01", "scene_02", …
        timestamp    (str)  "00:00 - 00:15"
        description  (str)  Korean scene description
        narration    (str)  spoken narration text
        image_prompt (str)  English prompt for Stable Diffusion
        video_prompt (str)  camera movement instructions
    """
    db = get_db()
    _update_progress(db, project_id, 4, 15, "스크립트 로드 중...")

    # ── 1. Fetch final_script ────────────────────────────────────────────────
    script_result = (
        db.table("scripts")
        .select("id, final_script")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not script_result.data or not script_result.data[0].get("final_script"):
        raise RuntimeError(
            f"No approved final_script found for project {project_id}. "
            "Complete Step 2 before running Step 4."
        )
    script_row = script_result.data[0]
    final_script: str = script_row["final_script"]
    script_id: str = script_row["id"]

    # ── 2. PdAgent → storyboard scenes ──────────────────────────────────────
    logger.info(f"[step4] Generating storyboard for project {project_id}")
    _update_progress(db, project_id, 4, 30, "스토리보드 생성 중...")
    _check_cancel(project_id, 4)
    agent = PdAgent()
    # Limit script to 6000 chars to prevent JSON truncation in storyboard output
    scenes: list[dict] = await agent.create_storyboard(final_script[:6000])
    if not scenes:
        raise RuntimeError("PdAgent returned an empty storyboard")
    logger.info(f"[step4] {len(scenes)} scenes received")

    # ── 3. Delete any previous storyboard rows for this project ─────────────
    db.table("assets").delete().eq("project_id", project_id).eq(
        "asset_type", "storyboard"
    ).execute()

    # ── 4. Insert one assets row per scene ───────────────────────────────────
    _update_progress(db, project_id, 4, 75, f"{len(scenes)}개 씬 저장 중...")
    for scene in scenes:
        scene_num = _scene_id_to_int(scene.get("scene_id", 0))
        db.table("assets").insert(
            {
                "project_id": project_id,
                "asset_type": "storyboard",
                "scene_id": scene_num,
                "metadata": scene,   # full scene dict in JSONB
            }
        ).execute()

    logger.info(
        f"[step4] {len(scenes)} storyboard assets inserted (project {project_id})"
    )

    _update_progress(db, project_id, 4, 95, "스토리보드 완료")


async def _step5_images_video(project_id: str, payload: dict) -> None:
    """Generate images and optional video clips for every storyboard scene.

    Flow per scene (concurrent, max 2 in-flight):
      1. Read image_prompt + video_prompt from assets (asset_type='storyboard')
      2. DALL-E 3 / Stability AI → image bytes
      3. Upload image to Supabase Storage → save assets row (type='image')
      4. (Optional) Runway ML / local SVD → video bytes
      5. Upload video to Supabase Storage → save assets row (type='video')

    Video generation is non-fatal: if the provider is not configured or fails,
    the step still completes successfully with images only.
    """
    from app.utils import storage, video_gen as video_gen_util

    db = get_db()
    genre = payload.get("genre", "general")
    provider_override = payload.get("image_provider", "")
    _update_progress(db, project_id, 5, 5, "스토리보드 로드 중...")

    # ── 1. Fetch storyboard scenes from assets ───────────────────────────────
    storyboard_result = (
        db.table("assets")
        .select("scene_id, metadata")
        .eq("project_id", project_id)
        .eq("asset_type", "storyboard")
        .order("scene_id")
        .execute()
    )
    scene_rows: list[dict] = storyboard_result.data or []
    if not scene_rows:
        raise RuntimeError(
            f"No storyboard found for project {project_id}. "
            "Complete Step 4 before running Step 5."
        )
    logger.info(
        f"[step5] {len(scene_rows)} scenes to process (project {project_id})"
    )

    # ── 2. Clear previous image / video assets for this project ─────────────
    for atype in ("image", "video"):
        db.table("assets").delete().eq("project_id", project_id).eq(
            "asset_type", atype
        ).execute()

    # ── 3. Per-scene processor (runs concurrently) ───────────────────────────
    completed_scenes = [0]
    semaphore = asyncio.Semaphore(2)  # max 2 concurrent API calls

    async def _process_scene(row: dict) -> None:
        async with semaphore:
            _check_cancel(project_id, 5)
            scene: dict = row.get("metadata") or {}
            scene_num: int = int(row["scene_id"])
            default_scene_id = f"scene_{scene_num:02d}"
            scene_id_str: str = scene.get("scene_id") or default_scene_id
            image_prompt: str = scene.get("image_prompt", "")
            video_prompt: str = scene.get("video_prompt", "slow pan right")

            if not image_prompt:
                logger.warning(
                    f"[step5] No image_prompt for {scene_id_str} — skipping"
                )
                return

            # ── Image generation ─────────────────────────────────────────
            image_bytes: bytes | None = None
            try:
                image_bytes = await stable_diffusion.generate_image(
                    image_prompt, width=1792, height=1024,
                    genre=genre, provider_override=provider_override,
                )
                image_url = storage.upload_file(
                    project_id=project_id,
                    filename=f"scenes/{scene_id_str}_image.png",
                    data=image_bytes,
                    content_type="image/png",
                )
                db.table("assets").insert(
                    {
                        "project_id": project_id,
                        "asset_type": "image",
                        "scene_id": scene_num,
                        "file_path": image_url,
                        "metadata": {
                            "scene_id": scene_id_str,
                            "image_prompt": image_prompt,
                        },
                    }
                ).execute()
                logger.info(f"[step5] Image saved: {scene_id_str}")
                completed_scenes[0] += 1
                pct = 10 + int((completed_scenes[0] / len(scene_rows)) * 80)
                _update_progress(db, project_id, 5, pct, f"씬 처리 중 ({completed_scenes[0]}/{len(scene_rows)}): {scene_id_str}")
            except Exception as exc:
                logger.error(
                    f"[step5] Image generation failed for {scene_id_str}: {exc}"
                )

            # ── Video generation (non-fatal) ─────────────────────────────
            if image_bytes is None:
                return  # can't make video without an image

            try:
                video_bytes = await video_gen_util.generate_video(
                    image_bytes=image_bytes,
                    video_prompt=video_prompt,
                    duration_seconds=5,
                )
                video_url = storage.upload_file(
                    project_id=project_id,
                    filename=f"scenes/{scene_id_str}_video.mp4",
                    data=video_bytes,
                    content_type="video/mp4",
                )
                db.table("assets").insert(
                    {
                        "project_id": project_id,
                        "asset_type": "video",
                        "scene_id": scene_num,
                        "file_path": video_url,
                        "metadata": {
                            "scene_id": scene_id_str,
                            "video_prompt": video_prompt,
                        },
                    }
                ).execute()
                logger.info(f"[step5] Video saved: {scene_id_str}")
            except NotImplementedError:
                logger.info(
                    f"[step5] Video provider not configured — "
                    f"skipping video for {scene_id_str}"
                )
            except Exception as exc:
                logger.warning(
                    f"[step5] Video generation failed for {scene_id_str}: {exc}"
                )

    # ── 4. Run all scenes concurrently ───────────────────────────────────────
    results = await asyncio.gather(
        *[_process_scene(row) for row in scene_rows],
        return_exceptions=True,
    )
    errors = [r for r in results if isinstance(r, Exception)]
    if errors:
        for err in errors:
            logger.error(f"[step5] Scene task exception: {err}")

    _update_progress(db, project_id, 5, 95, "최종 확인 중...")
    logger.info(
        f"[step5] Done — "
        f"{len(scene_rows) - len(errors)}/{len(scene_rows)} scenes succeeded"
    )


async def _step6_editing(project_id: str, payload: dict) -> None:
    """FFmpeg editing pipeline: concat clips → merge TTS audio → attach subtitles → upload.

    Flow:
      1. Read voice + caption URLs from assets
      2. Read video + image asset rows (for per-scene media)
      3. Read storyboard rows (for per-scene duration/timestamps)
      4. build_final_video() → MP4 bytes
      5. Upload final MP4 to Supabase Storage → save as assets (type='final_video')
      6. Strategist.generate_youtube_meta() → title / description / tags
      7. Save to youtube_meta table
    """
    from app.utils import storage as storage_util
    from app.utils.ffmpeg_editor import build_final_video

    db = get_db()
    _update_progress(db, project_id, 6, 10, "에셋 로드 중...")
    burn_subtitles: bool = bool(payload.get("burn_subtitles", False))

    # ── 1. Fetch voice & caption asset URLs ──────────────────────────────────
    assets_result = (
        db.table("assets")
        .select("asset_type, file_path")
        .eq("project_id", project_id)
        .in_("asset_type", ["voice", "caption"])
        .order("created_at", desc=True)
        .execute()
    )
    asset_rows: list[dict] = assets_result.data or []

    voice_url: str | None = next(
        (r["file_path"] for r in asset_rows if r["asset_type"] == "voice"), None
    )
    caption_url: str | None = next(
        (r["file_path"] for r in asset_rows if r["asset_type"] == "caption"), None
    )
    if not voice_url:
        raise RuntimeError(
            f"No voice asset found for project {project_id}. "
            "Complete Step 3 before running Step 6."
        )

    # ── 2. Fetch video + image asset rows ────────────────────────────────────
    media_result = (
        db.table("assets")
        .select("asset_type, scene_id, file_path, metadata")
        .eq("project_id", project_id)
        .in_("asset_type", ["image", "video"])
        .order("scene_id")
        .execute()
    )
    media_rows: list[dict] = media_result.data or []
    video_rows = [r for r in media_rows if r["asset_type"] == "video"]
    image_rows = [r for r in media_rows if r["asset_type"] == "image"]

    # ── 3. Fetch storyboard rows (timestamps → durations) ────────────────────
    sb_result = (
        db.table("assets")
        .select("scene_id, metadata")
        .eq("project_id", project_id)
        .eq("asset_type", "storyboard")
        .order("scene_id")
        .execute()
    )
    storyboard_rows: list[dict] = sb_result.data or []

    if not storyboard_rows:
        raise RuntimeError(
            f"No storyboard found for project {project_id}. "
            "Complete Step 4 before running Step 6."
        )

    logger.info(
        f"[step6] Starting ffmpeg pipeline — "
        f"{len(storyboard_rows)} scenes, "
        f"burn_subtitles={burn_subtitles} (project {project_id})"
    )

    # ── 4. Build final video ──────────────────────────────────────────────────
    _update_progress(db, project_id, 6, 30, "FFmpeg 편집 중...")
    _check_cancel(project_id, 6)
    final_bytes: bytes = await build_final_video(
        voice_url=voice_url,
        caption_url=caption_url,
        video_rows=video_rows,
        image_rows=image_rows,
        storyboard_rows=storyboard_rows,
        burn_subtitles=burn_subtitles,
    )
    logger.info(
        f"[step6] ffmpeg done — {len(final_bytes) / 1_048_576:.1f} MB "
        f"(project {project_id})"
    )

    # ── 5. Upload final MP4 ───────────────────────────────────────────────────
    _update_progress(db, project_id, 6, 70, "최종 영상 업로드 중...")
    video_url: str = storage_util.upload_file(
        project_id=project_id,
        filename="final_video.mp4",
        data=final_bytes,
        content_type="video/mp4",
    )
    db.table("assets").insert(
        {
            "project_id": project_id,
            "asset_type": "final_video",
            "file_path": video_url,
            "metadata": {
                "burn_subtitles": burn_subtitles,
                "size_bytes": len(final_bytes),
                "scenes": len(storyboard_rows),
            },
        }
    ).execute()
    logger.info(f"[step6] Final video uploaded → {video_url}")

    # ── 6. Generate YouTube metadata ──────────────────────────────────────────
    script_result = (
        db.table("scripts")
        .select("final_script, planning_doc")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    final_script: str = ""
    planning_doc: dict = {}
    if script_result.data:
        row = script_result.data[0]
        final_script = row.get("final_script") or ""
        raw_pd = row.get("planning_doc") or {}
        planning_doc = (
            json.loads(raw_pd) if isinstance(raw_pd, str) else raw_pd
        )

    logger.info(f"[step6] Generating YouTube metadata (project {project_id})")
    _update_progress(db, project_id, 6, 85, "YouTube 메타데이터 생성 중...")
    agent = StrategistAgent()
    youtube_meta: dict = await agent.generate_youtube_meta(final_script, planning_doc)

    # ── 7. Save youtube_meta row ──────────────────────────────────────────────
    _update_progress(db, project_id, 6, 95, "저장 중...")
    db.table("youtube_meta").upsert(
        {
            "project_id": project_id,
            "title": youtube_meta.get("title", ""),
            "description": youtube_meta.get("description", ""),
            "tags": youtube_meta.get("tags", []),
            "final_video_url": video_url,
        },
        on_conflict="project_id",
    ).execute()
    logger.info(
        f"[step6] YouTube metadata saved — title: {youtube_meta.get('title', '')!r} "
        f"(project {project_id})"
    )


async def _step7_thumbnail(project_id: str, payload: dict) -> None:
    """Thumbnail generation pipeline.

    Flow:
      1. Fetch youtube_meta (title) + benchmarking analysis_result
      2. Strategist.generate_thumbnail_prompt() → image prompt + overlay_text
      3. Stable Diffusion / DALL-E → 1280×720 image bytes
      4. Upload to Supabase Storage → assets row (asset_type='thumbnail')
      5. Update youtube_meta.thumbnail_url
    """
    from app.utils import storage as storage_util

    db = get_db()
    _update_progress(db, project_id, 7, 15, "데이터 로드 중...")

    # ── 1. Fetch YouTube title from youtube_meta ──────────────────────────────
    meta_result = (
        db.table("youtube_meta")
        .select("title")
        .eq("project_id", project_id)
        .limit(1)
        .execute()
    )
    youtube_title: str = (
        meta_result.data[0].get("title", "") if meta_result.data else ""
    )
    if not youtube_title:
        logger.warning(
            f"[step7] No youtube_meta title found for project {project_id} — "
            "proceeding with empty title"
        )

    # ── 2. Fetch benchmarking analysis_result ─────────────────────────────────
    bench_result = (
        db.table("benchmarking")
        .select("analysis_result")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    analysis_raw = bench_result.data[0].get("analysis_result") if bench_result.data else {}
    analysis_result: dict = (
        json.loads(analysis_raw) if isinstance(analysis_raw, str) else (analysis_raw or {})
    )

    # ── 3. Strategist → thumbnail prompt ─────────────────────────────────────
    logger.info(f"[step7] Generating thumbnail prompt for project {project_id}")
    _update_progress(db, project_id, 7, 30, "썸네일 프롬프트 생성 중...")
    _check_cancel(project_id, 7)
    agent = StrategistAgent()
    thumb_spec: dict = await agent.generate_thumbnail_prompt(
        youtube_title=youtube_title,
        analysis_result=analysis_result,
    )
    image_prompt: str = thumb_spec.get("prompt", "")
    overlay_text: str = thumb_spec.get("overlay_text", "")
    style_notes: str = thumb_spec.get("style_notes", "")

    logger.info(
        f"[step7] Thumbnail prompt: {image_prompt[:120]!r} "
        f"overlay='{overlay_text}' (project {project_id})"
    )

    # ── 4. Stable Diffusion / DALL-E → image bytes ───────────────────────────
    # YouTube thumbnail is 1280×720 (16:9).
    # DALL-E 3 only supports 1792×1024 / 1024×1024 / 1024×1792 — use 1792×1024
    # and let the frontend crop/display at 16:9.  Stability AI returns exact sizes.
    _update_progress(db, project_id, 7, 55, "AI 이미지 생성 중...")
    image_bytes: bytes = await stable_diffusion.generate_image(
        image_prompt, width=1280, height=720
    )
    logger.info(
        f"[step7] Thumbnail image generated — {len(image_bytes) / 1024:.0f} KB "
        f"(project {project_id})"
    )

    # ── 5. Upload to Supabase Storage ─────────────────────────────────────────
    _update_progress(db, project_id, 7, 85, "썸네일 업로드 중...")
    thumbnail_url: str = storage_util.upload_file(
        project_id=project_id,
        filename="thumbnail.png",
        data=image_bytes,
        content_type="image/png",
    )

    # ── 6. Save assets row ────────────────────────────────────────────────────
    # Remove any previous thumbnail for this project first
    db.table("assets").delete().eq("project_id", project_id).eq(
        "asset_type", "thumbnail"
    ).execute()

    db.table("assets").insert(
        {
            "project_id": project_id,
            "asset_type": "thumbnail",
            "file_path": thumbnail_url,
            "metadata": {
                "image_prompt": image_prompt,
                "overlay_text": overlay_text,
                "style_notes": style_notes,
                "youtube_title": youtube_title,
                "size_bytes": len(image_bytes),
            },
        }
    ).execute()
    logger.info(f"[step7] Thumbnail asset saved → {thumbnail_url}")

    # ── 7. Update youtube_meta.thumbnail_url ─────────────────────────────────
    db.table("youtube_meta").update(
        {"thumbnail_url": thumbnail_url}
    ).eq("project_id", project_id).execute()
    logger.info(f"[step7] youtube_meta.thumbnail_url updated (project {project_id})")


async def _step8_export_upload(project_id: str, payload: dict) -> None:
    """YouTube export + upload pipeline.

    Flow:
      1. Load OAuth2 token — from YOUTUBE_OAUTH_TOKEN_JSON env var
      2. Fetch final_video + thumbnail asset URLs from assets table
      3. Fetch youtube_meta (title, description, tags)
      4. Download video + thumbnail bytes via httpx
      5. upload_video_bytes() → youtube_video_id
      6. set_thumbnail() (non-fatal if thumbnail missing or API fails)
      7. Save youtube_video_id to projects + youtube_meta
      8. Mark project complete (current_step=9 handled by run_step)

    Payload optional overrides:
      privacy_status  (str)  "private" | "unlisted" | "public"  (default "private")
      category_id     (str)  YouTube category ID                 (default "22")
    """
    import os as _os
    from app.utils.ffmpeg_editor import download_file as _download_file

    db = get_db()
    _update_progress(db, project_id, 8, 10, "업로드 준비 중...")

    # ── 1. OAuth2 token (optional — skip upload if not set) ──────────────────
    token_json: str = _os.getenv("YOUTUBE_OAUTH_TOKEN_JSON", "")
    skip_upload: bool = not token_json
    if skip_upload:
        logger.warning(
            "[step8] YOUTUBE_OAUTH_TOKEN_JSON not set — "
            "skipping YouTube upload. "
            "Run GET /auth/youtube to configure OAuth2."
        )

    # ── 2. Fetch asset URLs ───────────────────────────────────────────────────
    assets_result = (
        db.table("assets")
        .select("asset_type, file_path")
        .eq("project_id", project_id)
        .in_("asset_type", ["final_video", "thumbnail"])
        .order("created_at", desc=True)
        .execute()
    )
    asset_rows: list[dict] = assets_result.data or []

    final_video_url: str | None = next(
        (r["file_path"] for r in asset_rows if r["asset_type"] == "final_video"), None
    )
    thumbnail_url: str | None = next(
        (r["file_path"] for r in asset_rows if r["asset_type"] == "thumbnail"), None
    )
    if not final_video_url:
        raise RuntimeError(
            f"No final_video asset found for project {project_id}. "
            "Complete Step 6 before running Step 8."
        )

    # ── 3. Fetch youtube_meta ─────────────────────────────────────────────────
    meta_result = (
        db.table("youtube_meta")
        .select("title, description, tags")
        .eq("project_id", project_id)
        .limit(1)
        .execute()
    )
    if not meta_result.data:
        raise RuntimeError(
            f"No youtube_meta found for project {project_id}. "
            "Complete Step 6 before running Step 8."
        )
    meta = meta_result.data[0]
    # Allow payload to override AI-generated youtube_meta values
    title: str = payload.get("title") or meta.get("title") or "AutoVidPro Video"
    description: str = payload.get("description") or meta.get("description") or ""
    tags_raw_payload = payload.get("tags")
    if tags_raw_payload:
        tags: list[str] = (
            tags_raw_payload
            if isinstance(tags_raw_payload, list)
            else [t.strip() for t in str(tags_raw_payload).split(",") if t.strip()]
        )
    else:
        tags_raw = meta.get("tags") or []
        # tags may be stored as a JSON string or a list
        if isinstance(tags_raw, str):
            try:
                tags = json.loads(tags_raw)
            except Exception:
                tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
        else:
            tags = list(tags_raw)

    # ── 4. Download video + thumbnail bytes ───────────────────────────────────
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as _tmp:
        tmpdir = Path(_tmp)

        _update_progress(db, project_id, 8, 25, "영상 다운로드 중...")
        _check_cancel(project_id, 8)
        logger.info(f"[step8] Downloading final video… (project {project_id})")
        video_path = tmpdir / "final_video.mp4"
        await _download_file(final_video_url, video_path)
        video_bytes: bytes = video_path.read_bytes()
        logger.info(f"[step8] Video downloaded — {len(video_bytes) / 1_048_576:.1f} MB")

        thumbnail_bytes: bytes | None = None
        if thumbnail_url:
            logger.info(f"[step8] Downloading thumbnail…")
            thumb_path = tmpdir / "thumbnail.png"
            try:
                await _download_file(thumbnail_url, thumb_path)
                thumbnail_bytes = thumb_path.read_bytes()
                logger.info(
                    f"[step8] Thumbnail downloaded — {len(thumbnail_bytes) / 1024:.0f} KB"
                )
            except Exception as exc:
                logger.warning(f"[step8] Thumbnail download failed (non-fatal): {exc}")

        # ── 5. Upload video to YouTube (skip if no OAuth token) ───────────────
        privacy_status: str = payload.get("privacy_status") or payload.get("privacy", "private")
        category_id: str = str(payload.get("category_id", "22"))

        youtube_video_id: str = ""
        if skip_upload:
            _update_progress(db, project_id, 8, 80, "YouTube OAuth 미설정 — 업로드 건너뜀")
            logger.warning("[step8] Skipping YouTube upload — no OAuth token")
        else:
            logger.info(
                f"[step8] Uploading to YouTube — "
                f"title={title!r}, privacy={privacy_status} (project {project_id})"
            )
            _update_progress(db, project_id, 8, 45, "YouTube 업로드 중...")
            youtube_video_id = await youtube_api.upload_video_bytes(
                video_bytes=video_bytes,
                title=title,
                description=description,
                tags=tags,
                token_json=token_json,
                category_id=category_id,
                privacy_status=privacy_status,
            )
            logger.info(
                f"[step8] YouTube upload complete — "
                f"video_id={youtube_video_id} (project {project_id})"
            )

        # ── 6. Set custom thumbnail (non-fatal, only if upload happened) ──────
        _update_progress(db, project_id, 8, 80, "썸네일 설정 중...")
        if thumbnail_bytes and youtube_video_id:
            try:
                await youtube_api.set_thumbnail(
                    video_id=youtube_video_id,
                    thumbnail_bytes=thumbnail_bytes,
                    token_json=token_json,
                )
                logger.info(f"[step8] Custom thumbnail set for {youtube_video_id}")
            except Exception as exc:
                logger.warning(
                    f"[step8] Thumbnail upload failed (non-fatal): {exc}. "
                    "You can set it manually in YouTube Studio."
                )

    # ── 7. Persist youtube_video_id ───────────────────────────────────────────
    _update_progress(db, project_id, 8, 95, "완료 처리 중...")
    db.table("projects").update(
        {"youtube_video_id": youtube_video_id}
    ).eq("id", project_id).execute()

    db.table("youtube_meta").update(
        {"youtube_video_id": youtube_video_id}
    ).eq("project_id", project_id).execute()

    logger.info(
        f"[step8] Project complete — "
        f"youtube_video_id={youtube_video_id} (project {project_id})"
    )
