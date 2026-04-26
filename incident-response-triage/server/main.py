from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Any, Optional
import os

from server.models import Action, Observation, Reward, EnvironmentState
from server.environment import IncidentResponseEnvironment

app = FastAPI(
    title="Incident Response Triage — OpenEnv",
    description="An OpenEnv environment where AI agents learn to triage production incidents.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Single shared environment instance (stateful, single-user for hackathon)
env = IncidentResponseEnvironment()


# ── Request/Response schemas ───────────────────────────────────────────────────

class ResetRequest(BaseModel):
    task_id: str = "task1_easy"


class StepResponse(BaseModel):
    observation: Observation
    reward: Reward
    done: bool
    info: dict[str, Any]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/reset", response_model=Observation)
def reset(request: Optional[ResetRequest] = None):
    """Start a new episode. Returns the initial observation."""
    task_id = (request.task_id if request else None) or "task1_easy"
    try:
        obs = env.reset(task_id=task_id)
        return obs
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/step", response_model=StepResponse)
def step(action: Action):
    """Take one action. Returns observation, reward, done flag, and info."""
    try:
        obs, reward, done, info = env.step(action)
        return StepResponse(observation=obs, reward=reward, done=done, info=info)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/state", response_model=EnvironmentState)
def state():
    """Return the current environment state without modifying it."""
    return env.state()


@app.get("/tasks")
def list_tasks():
    """List all available tasks with difficulty and description."""
    return env.list_tasks()


@app.get("/health")
def health():
    return {"status": "ok", "environment": "incident-response-triage", "version": "1.0.0"}


@app.get("/")
def root():
    static_index = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(static_index):
        return FileResponse(static_index)
    return {
        "name": "Incident Response Triage OpenEnv",
        "endpoints": ["/reset", "/step", "/state", "/tasks", "/health"],
        "docs": "/docs",
    }


# Mount static files (dashboard UI)
_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")
