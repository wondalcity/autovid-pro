from dotenv import load_dotenv
load_dotenv()

import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import projects, steps, auth, settings

logger = logging.getLogger(__name__)


def _recover_stuck_steps() -> None:
    """On startup, reset any step_logs stuck in 'running' back to 'pending'.

    This happens when the server is killed or restarted mid-step.
    """
    try:
        from app.database import get_db
        db = get_db()
        result = db.table("step_logs").update(
            {"status": "pending", "progress": 0, "message": "서버 재시작으로 인해 초기화됨"}
        ).eq("status", "running").execute()
        if result.data:
            logger.warning(
                f"[startup] Reset {len(result.data)} stuck 'running' step(s) → 'pending'"
            )
    except Exception as exc:
        logger.warning(f"[startup] Step recovery failed (non-fatal): {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _recover_stuck_steps()
    yield


app = FastAPI(title="AutoVidPro API", version="0.1.0", lifespan=lifespan)

frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router, prefix="/projects", tags=["projects"])
app.include_router(steps.router, prefix="/projects", tags=["steps"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(settings.router, prefix="/settings", tags=["settings"])


@app.get("/")
async def health_check():
    return {"status": "ok"}
