from fastapi import APIRouter, BackgroundTasks, HTTPException
from app.models import StepRunRequest, StepStatus, ScriptApproveRequest
from app.services.step_runner import run_step, _upsert_step_log
from app.database import get_db

router = APIRouter()


@router.post("/{project_id}/steps/{step_num}/run")
async def run_step_endpoint(
    project_id: str,
    step_num: int,
    body: StepRunRequest,
    background_tasks: BackgroundTasks,
):
    payload = body.payload or {}
    background_tasks.add_task(run_step, project_id, step_num, payload)
    return {"status": "started"}


@router.get("/{project_id}/steps/{step_num}/status", response_model=StepStatus)
async def get_step_status(project_id: str, step_num: int):
    db = get_db()

    # Prefer step_logs for accurate per-step status
    try:
        log_result = (
            db.table("step_logs")
            .select("status, message, progress")
            .eq("project_id", project_id)
            .eq("step_num", step_num)
            .execute()
        )
        if log_result.data:
            row = log_result.data[0]
            return StepStatus(
                project_id=project_id,
                step_num=step_num,
                status=row["status"],
                message=row.get("message"),
                progress=row.get("progress", 0),
            )
    except Exception:
        pass  # step_logs table may not exist yet — fall through to current_step fallback

    # Fallback: derive from current_step
    result = db.table("projects").select("current_step").eq("id", project_id).execute()
    if not result.data:
        return StepStatus(
            project_id=project_id,
            step_num=step_num,
            status="error",
            message="Project not found",
        )
    current_step = result.data[0]["current_step"]
    if current_step > step_num:
        status = "done"
    elif current_step == step_num:
        status = "running"
    else:
        status = "pending"
    return StepStatus(project_id=project_id, step_num=step_num, status=status)


@router.get("/{project_id}/steps/{step_num}/data")
async def get_step_data(project_id: str, step_num: int):
    db = get_db()

    if step_num == 1:
        # Return all benchmarked videos + analysis from the latest run
        all_rows = (
            db.table("benchmarking")
            .select("youtube_url, title, analysis_result, transcript, created_at")
            .eq("project_id", project_id)
            .order("created_at", desc=False)
            .execute()
        )
        rows = all_rows.data or []
        # Filter out malformed rows (single-char URLs from old bug)
        rows = [r for r in rows if r.get("youtube_url") and len(r["youtube_url"]) > 10]
        if not rows:
            return {}

        # Pick the row that has the combined analysis_result
        analysis_row = next((r for r in reversed(rows) if r.get("analysis_result")), rows[-1])
        # Build video list with transcript excerpt and key facts from analysis
        ar = analysis_row.get("analysis_result") or {}
        key_facts = ar.get("key_facts") or []
        return {
            "analysis_result": ar,
            "benchmarked_videos": [
                {
                    "url": r["youtube_url"],
                    "title": r.get("title", ""),
                    "created_at": r.get("created_at", ""),
                    "transcript_excerpt": (r.get("transcript") or "")[:300],
                }
                for r in rows
            ],
            "key_facts": key_facts,
        }

    if step_num == 2:
        result = (
            db.table("scripts")
            .select("hook_intro, raw_script, ctr_design_ideas, final_script")
            .eq("project_id", project_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else {}

    if step_num == 3:
        result = (
            db.table("assets")
            .select("asset_type, file_path, metadata")
            .eq("project_id", project_id)
            .in_("asset_type", ["voice", "caption"])
            .order("created_at", desc=True)
            .execute()
        )
        assets = result.data or []
        return {
            "voice": next((a for a in assets if a["asset_type"] == "voice"), None),
            "caption": next((a for a in assets if a["asset_type"] == "caption"), None),
        }

    if step_num == 4:
        result = (
            db.table("assets")
            .select("scene_id, metadata")
            .eq("project_id", project_id)
            .eq("asset_type", "storyboard")
            .order("scene_id")
            .execute()
        )
        return {"scenes": result.data or []}

    if step_num == 5:
        result = (
            db.table("assets")
            .select("asset_type, scene_id, file_path, metadata")
            .eq("project_id", project_id)
            .in_("asset_type", ["image", "video"])
            .order("scene_id")
            .execute()
        )
        # Group rows by scene_id → { scene_id, image: row|None, video: row|None }
        scenes_map: dict = {}
        for row in (result.data or []):
            sid = row["scene_id"]
            if sid not in scenes_map:
                scenes_map[sid] = {"scene_id": sid, "image": None, "video": None}
            scenes_map[sid][row["asset_type"]] = row
        scenes = sorted(scenes_map.values(), key=lambda x: x["scene_id"] or 0)
        return {"scenes": scenes}

    if step_num == 6:
        # Final video asset
        video_result = (
            db.table("assets")
            .select("file_path, metadata")
            .eq("project_id", project_id)
            .eq("asset_type", "final_video")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        # YouTube metadata
        meta_result = (
            db.table("youtube_meta")
            .select("title, description, tags, final_video_url")
            .eq("project_id", project_id)
            .limit(1)
            .execute()
        )
        return {
            "final_video": video_result.data[0] if video_result.data else None,
            "youtube_meta": meta_result.data[0] if meta_result.data else None,
        }

    if step_num == 7:
        thumb_result = (
            db.table("assets")
            .select("file_path, metadata")
            .eq("project_id", project_id)
            .eq("asset_type", "thumbnail")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return thumb_result.data[0] if thumb_result.data else {}

    if step_num == 8:
        proj_result = (
            db.table("projects")
            .select("youtube_video_id")
            .eq("id", project_id)
            .execute()
        )
        meta_result = (
            db.table("youtube_meta")
            .select("title, description, tags, thumbnail_url, youtube_video_id")
            .eq("project_id", project_id)
            .limit(1)
            .execute()
        )
        youtube_video_id: str = (
            (proj_result.data[0].get("youtube_video_id") if proj_result.data else None)
            or (meta_result.data[0].get("youtube_video_id") if meta_result.data else None)
            or ""
        )
        return {
            "youtube_video_id": youtube_video_id,
            "youtube_meta": meta_result.data[0] if meta_result.data else None,
        }

    raise HTTPException(status_code=400, detail=f"Invalid step_num: {step_num}")


# ─── Step 2: manual approval ─────────────────────────────────────────────────

@router.post("/{project_id}/steps/2/approve")
async def approve_script(project_id: str, body: ScriptApproveRequest):
    """Save the user-edited final script and advance the project to Step 3.

    - Writes body.final_script → scripts.final_script (latest row)
    - Updates projects.current_step → 3
    - Records step_logs step 2 as 'approved'
    """
    if not body.final_script.strip():
        raise HTTPException(status_code=422, detail="final_script must not be empty")

    db = get_db()

    # Find the latest scripts row for this project
    script_result = (
        db.table("scripts")
        .select("id")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not script_result.data:
        raise HTTPException(status_code=404, detail="No script found for this project")
    script_id = script_result.data[0]["id"]

    # Persist the approved final script
    db.table("scripts").update(
        {"final_script": body.final_script}
    ).eq("id", script_id).execute()

    # Advance project step
    db.table("projects").update({"current_step": 3}).eq("id", project_id).execute()

    # Mark step 2 as approved in step_logs
    _upsert_step_log(db, project_id, step_num=2, status="done", message="approved")

    return {"approved": True, "script_id": script_id}


@router.post("/{project_id}/steps/{step_num}/cancel")
async def cancel_step(project_id: str, step_num: int):
    """Cancel a running step and reset it to pending."""
    from app.services.step_runner import request_cancel
    request_cancel(project_id, step_num)
    db = get_db()
    _upsert_step_log(db, project_id, step_num, "pending", "사용자에 의해 취소됨", 0)
    # Reset current_step back to this step (undo auto-advance if any)
    db.table("projects").update({"current_step": step_num}).eq("id", project_id).execute()
    return {"status": "cancelled", "step_num": step_num}
