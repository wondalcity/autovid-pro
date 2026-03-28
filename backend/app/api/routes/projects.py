from fastapi import APIRouter, HTTPException
from app.models import ProjectCreate, ProjectResponse
from app.database import get_db

router = APIRouter()


@router.post("/", response_model=ProjectResponse)
async def create_project(body: ProjectCreate):
    db = get_db()
    result = (
        db.table("projects")
        .insert({"title": body.title, "current_step": 0})
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create project")
    row = result.data[0]
    return ProjectResponse(
        id=row["id"],
        title=row["title"],
        created_at=row["created_at"],
        current_step=row["current_step"],
    )


@router.get("/", response_model=list[ProjectResponse])
async def list_projects():
    db = get_db()
    result = db.table("projects").select("*").order("created_at", desc=True).execute()
    return [
        ProjectResponse(
            id=row["id"],
            title=row["title"],
            created_at=row["created_at"],
            current_step=row["current_step"],
        )
        for row in (result.data or [])
    ]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str):
    db = get_db()
    result = db.table("projects").select("*").eq("id", project_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Project not found")
    row = result.data[0]
    return ProjectResponse(
        id=row["id"],
        title=row["title"],
        created_at=row["created_at"],
        current_step=row["current_step"],
    )


@router.delete("/{project_id}")
async def delete_project(project_id: str):
    db = get_db()
    result = db.table("projects").delete().eq("id", project_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"deleted": True, "id": project_id}
