from dotenv import load_dotenv
load_dotenv()

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import projects, steps, auth

app = FastAPI(title="AutoVidPro API", version="0.1.0")

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


@app.get("/")
async def health_check():
    return {"status": "ok"}
