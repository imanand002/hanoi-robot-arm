"""
service.py  --  The "helper" between the web API and the algorithms.

It keeps simulations in memory, compares algorithms and validates moves.
It has NO web code inside, so it is easy to test on its own.
"""

import uuid
from collections import OrderedDict
from typing import Dict, List

from .algorithms import ALGORITHMS, PEG_NAMES, best_time_ms, min_moves, run_algorithm
from .game import Game, GameError
from .validator import InvalidMoveError, initial_pegs, validate_solution

MAX_ANIMATED_DISKS = 10   # 2^10 - 1 = 1023 moves: fine to animate
MAX_COMPARE_DISKS = 20    # 2^20 - 1 = 1,048,575 moves: fine to just time
MAX_SERIES_DISKS = 18     # keeps the chart request quick
MAX_STORED_SIMULATIONS = 100

# Remember the most recent simulations (oldest ones get forgotten).
_simulations: "OrderedDict[str, dict]" = OrderedDict()


class ServiceError(Exception):
    """Friendly error that the API turns into an HTTP error."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _check_algorithm(name: str) -> None:
    if name not in ALGORITHMS:
        raise ServiceError(f"Unknown algorithm '{name}'. Choose: {', '.join(ALGORITHMS)}.", 422)


def _check_disks(n: int, maximum: int) -> None:
    if not isinstance(n, int) or n < 1 or n > maximum:
        raise ServiceError(f"Number of disks must be a whole number from 1 to {maximum}.", 422)


def start_simulation(disks: int, algorithm: str) -> dict:
    """Solve the puzzle, double-check every move with the referee, store it."""
    _check_algorithm(algorithm)
    _check_disks(disks, MAX_ANIMATED_DISKS)

    result = run_algorithm(algorithm, disks)

    try:
        validate_solution(disks, result["moves"])
    except InvalidMoveError as err:  # should never happen, but we check anyway!
        raise ServiceError(f"Backend produced an invalid solution: {err}", 500)

    sim_id = uuid.uuid4().hex[:12]
    result.update(
        {
            "simulation_id": sim_id,
            "validated": True,
            "peg_names": PEG_NAMES,
            "state": "ready",
        }
    )
    _simulations[sim_id] = result
    while len(_simulations) > MAX_STORED_SIMULATIONS:
        _simulations.popitem(last=False)
    return result


def get_simulation(sim_id: str) -> dict:
    if sim_id not in _simulations:
        raise ServiceError(f"Simulation '{sim_id}' was not found. Press Start to make a new one.", 404)
    return _simulations[sim_id]


def reset_simulation(sim_id: str) -> dict:
    sim = get_simulation(sim_id)
    sim["state"] = "ready"
    return {
        "simulation_id": sim_id,
        "disks": sim["disks"],
        "algorithm": sim["algorithm"],
        "state": "ready",
        "pegs": initial_pegs(sim["disks"]),
        "message": "Simulation reset. All disks are back on peg A.",
    }


def compare(disks: int, repeats: int = 3) -> dict:
    """Run both algorithms on the same puzzle and compare."""
    _check_disks(disks, MAX_COMPARE_DISKS)
    repeats = max(1, min(int(repeats), 10))

    runs: Dict[str, dict] = {}
    for name in ALGORITHMS:
        info = run_algorithm(name, disks)  # keep the moves so we can compare them
        fastest = info["execution_time_ms"]
        for _ in range(repeats - 1):  # extra tries; keep the fastest time
            fastest = min(fastest, run_algorithm(name, disks)["execution_time_ms"])
        info["execution_time_ms"] = fastest
        runs[name] = info

    same_moves = runs["recursive"]["moves"] == runs["iterative"]["moves"]
    summary = {
        name: {
            "algorithm": name,
            "total_moves": r["total_moves"],
            "execution_time_ms": r["execution_time_ms"],
            "is_minimum": r["is_minimum"],
        }
        for name, r in runs.items()
    }
    rec_t = summary["recursive"]["execution_time_ms"]
    ite_t = summary["iterative"]["execution_time_ms"]
    faster = "recursive" if rec_t < ite_t else "iterative" if ite_t < rec_t else "tie"
    return {
        "disks": disks,
        "min_moves": min_moves(disks),
        "results": summary,
        "same_moves": same_moves,
        "faster": faster,
        "repeats": repeats,
    }


def compare_series(max_disks: int, repeats: int = 3) -> dict:
    """Timing for 1..max_disks disks, used to draw the chart."""
    _check_disks(max_disks, MAX_SERIES_DISKS)
    points: List[dict] = []
    for n in range(1, max_disks + 1):
        points.append(
            {
                "disks": n,
                "moves": min_moves(n),
                "recursive_ms": best_time_ms("recursive", n, repeats),
                "iterative_ms": best_time_ms("iterative", n, repeats),
            }
        )
    return {"points": points, "repeats": repeats}


def validate_given_moves(disks: int, moves: List[dict]) -> dict:
    """Check a list of moves someone sends us."""
    _check_disks(disks, MAX_COMPARE_DISKS)
    try:
        validate_solution(disks, moves)
    except InvalidMoveError as err:
        return {"valid": False, "message": str(err)}
    return {"valid": True, "message": "All moves are legal and the puzzle is solved."}


# ===========================================================================
#  THE GAME  (a person plays; the backend is the referee and the coach)
# ===========================================================================
MAX_STORED_GAMES = 200
_games: "OrderedDict[str, Game]" = OrderedDict()


def _game(game_id: str) -> Game:
    if game_id not in _games:
        raise ServiceError(f"Game '{game_id}' was not found. Press New game to start one.", 404)
    return _games[game_id]


def _wrap(call):
    """Run a game action and turn GameError into ServiceError."""
    try:
        return call()
    except GameError as err:
        raise ServiceError(err.message, err.status_code)


def game_new(disks: int) -> dict:
    _check_disks(disks, MAX_ANIMATED_DISKS)
    game = Game(disks)
    _games[game.id] = game
    while len(_games) > MAX_STORED_GAMES:
        _games.popitem(last=False)
    return game.snapshot()


def game_get(game_id: str) -> dict:
    return _game(game_id).snapshot()


def game_move(game_id: str, src: int, dst: int) -> dict:
    game = _game(game_id)
    move = _wrap(lambda: game.apply_move(src, dst))
    return {"move": move, "game": game.snapshot()}


def game_undo(game_id: str) -> dict:
    game = _game(game_id)
    undone = _wrap(game.undo)
    return {"undone": undone, "game": game.snapshot()}


def game_hint(game_id: str) -> dict:
    game = _game(game_id)
    hint = _wrap(game.hint)
    return {"hint": hint, "game": game.snapshot()}


def game_restart(game_id: str) -> dict:
    game = _game(game_id)
    game.restart()
    return game.snapshot()


def game_solve(game_id: str) -> dict:
    """The robot finishes the puzzle from wherever the player stopped."""
    game = _game(game_id)
    moves = _wrap(game.solve_for_player)
    return {"moves": moves, "game": game.snapshot()}
