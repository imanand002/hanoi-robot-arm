"""
main.py  --  The web server (FastAPI).

Run it from the project folder with:
    uvicorn backend.main:app --reload
Then open http://127.0.0.1:8000
"""

from pathlib import Path
from typing import List

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import service
from .service import ServiceError

app = FastAPI(
    title="Tower of Hanoi Robotic Arm Game API",
    description=(
        "Play Tower of Hanoi with a robotic arm. Start a game, make moves (validated), "
        "ask for hints, undo, or let the robot solve it. Also solves with recursive/iterative "
        "algorithms and compares their speed."
    ),
    version="2.0.0",
)

# Allow the page to talk to us even if it is opened from a different place.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ---- Friendly error messages ------------------------------------------------
@app.exception_handler(ServiceError)
async def service_error_handler(_request, err: ServiceError):
    return JSONResponse(status_code=err.status_code, content={"detail": err.message})


# ---- What the browser may send us ------------------------------------------
class StartRequest(BaseModel):
    disks: int = Field(3, ge=1, le=service.MAX_ANIMATED_DISKS, description="Number of disks (1-10)")
    algorithm: str = Field("recursive", description="'recursive' or 'iterative'")


class CompareRequest(BaseModel):
    disks: int = Field(10, ge=1, le=service.MAX_COMPARE_DISKS)
    repeats: int = Field(3, ge=1, le=10, description="Tries per algorithm; the fastest is reported")


class GameNewRequest(BaseModel):
    disks: int = Field(3, ge=1, le=service.MAX_ANIMATED_DISKS, description="Number of disks (1-10)")


class MoveRequest(BaseModel):
    """A move the player wants to make:  {"from": 0, "to": 2}   (0=A, 1=B, 2=C)"""

    model_config = {"populate_by_name": True}

    from_rod: int = Field(..., alias="from", ge=0, le=2)
    to: int = Field(..., ge=0, le=2)


class ValidateRequest(BaseModel):
    # each move looks like {"disk": 1, "from": 0, "to": 2}
    disks: int = Field(..., ge=1, le=service.MAX_COMPARE_DISKS)
    moves: List[dict]


# ---- The API ---------------------------------------------------------------
@app.get("/api/health")
def health():
    """Is the server alive?"""
    return {"status": "ok"}


@app.post("/api/simulations/start")
def start(req: StartRequest):
    """Solve the puzzle and return every move (plus timing)."""
    return service.start_simulation(req.disks, req.algorithm)


@app.get("/api/simulations/{sim_id}")
def get_one(sim_id: str):
    return service.get_simulation(sim_id)


@app.post("/api/simulations/{sim_id}/reset")
def reset(sim_id: str):
    """Put all disks back on peg A."""
    return service.reset_simulation(sim_id)


@app.post("/api/compare")
def compare(req: CompareRequest):
    """Run both algorithms on the same puzzle and compare them."""
    return service.compare(req.disks, req.repeats)


@app.get("/api/compare/series")
def compare_series(
    max_disks: int = Query(14, ge=1, le=service.MAX_SERIES_DISKS),
    repeats: int = Query(3, ge=1, le=10),
):
    """Timings for 1..max_disks disks (for the chart)."""
    return service.compare_series(max_disks, repeats)


@app.post("/api/validate")
def validate(req: ValidateRequest):
    """Check a list of moves against the Tower of Hanoi rules."""
    return service.validate_given_moves(req.disks, req.moves)


# ---- The GAME API ----------------------------------------------------------
@app.post("/api/game/new")
def game_new(req: GameNewRequest):
    """Start a new game. Returns the board and a game_id."""
    return service.game_new(req.disks)


@app.get("/api/game/{game_id}")
def game_get(game_id: str):
    """Current board, counters and history of a game."""
    return service.game_get(game_id)


@app.post("/api/game/{game_id}/move")
def game_move(game_id: str, req: MoveRequest):
    """Make a move. Illegal moves are refused (HTTP 422) with a friendly message."""
    return service.game_move(game_id, req.from_rod, req.to)


@app.post("/api/game/{game_id}/hint")
def game_hint(game_id: str):
    """Ask for a hint: the best next move from the current position."""
    return service.game_hint(game_id)


@app.post("/api/game/{game_id}/undo")
def game_undo(game_id: str):
    """Take back the last move."""
    return service.game_undo(game_id)


@app.post("/api/game/{game_id}/restart")
def game_restart(game_id: str):
    """Start the same game over."""
    return service.game_restart(game_id)


@app.post("/api/game/{game_id}/solve")
def game_solve(game_id: str):
    """Let the robot finish the puzzle (no stars are earned)."""
    return service.game_solve(game_id)


# ---- Serve the web page (must be LAST so it does not hide /api) -------------
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
