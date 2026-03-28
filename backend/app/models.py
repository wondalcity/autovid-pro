from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class ProjectCreate(BaseModel):
    title: str


class ProjectResponse(BaseModel):
    id: str
    title: str
    created_at: str
    current_step: int


class BenchmarkingInput(BaseModel):
    project_id: str
    youtube_url: str


class ScriptInput(BaseModel):
    project_id: str
    story_concept: Optional[str] = None


class StepStatus(BaseModel):
    project_id: str
    step_num: int
    status: str  # pending | running | awaiting_review | done | error
    message: Optional[str] = None
    progress: Optional[int] = None


class StepRunRequest(BaseModel):
    project_id: Optional[str] = None  # redundant with URL param; kept for backwards-compat
    payload: Optional[dict] = None


class ScriptApproveRequest(BaseModel):
    final_script: str
