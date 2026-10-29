"""
game.py  --  One game of Tower of Hanoi that a person plays.

A Game remembers the rods, the moves made, hints used and the clock.
It has NO web code inside, so it is easy to test on its own.
"""

import time
import uuid
from typing import Dict, List, Optional

from .algorithms import min_moves
from .hints import full_hint, moves_remaining, next_move
from .validator import check_move, initial_pegs


class GameError(Exception):
    """A friendly problem (illegal move, game already solved, ...)."""

    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class Game:
    def __init__(self, disks: int):
        self.id = uuid.uuid4().hex[:12]
        self.disks = disks
        self.pegs: List[List[int]] = initial_pegs(disks)
        self.history: List[Dict[str, int]] = []   # moves currently on the board
        self.moves_made = 0                        # every move ever made (undo does not erase it)
        self.hints_used = 0
        self.undos = 0
        self.invalid_attempts = 0
        self.assisted = False                      # True if the robot solved it
        self.solved = False
        self.started_at: Optional[float] = None
        self.finished_at: Optional[float] = None

    # ---- playing -------------------------------------------------------
    def _must_be_playing(self) -> None:
        if self.solved:
            raise GameError("This puzzle is already solved. Start a new game or press Restart.", 409)

    def apply_move(self, src: int, dst: int) -> Dict[str, int]:
        """Make one move if the rules allow it, otherwise raise GameError."""
        self._must_be_playing()
        problem = check_move(self.pegs, src, dst)
        if problem:
            self.invalid_attempts += 1
            raise GameError(problem, 422)

        if self.started_at is None:
            self.started_at = time.time()
        disk = self.pegs[src].pop()
        self.pegs[dst].append(disk)
        move = {"disk": disk, "from": src, "to": dst}
        self.history.append(move)
        self.moves_made += 1

        if self.pegs[2] == list(range(self.disks, 0, -1)):
            self.solved = True
            self.finished_at = time.time()
        return move

    def undo(self) -> Dict[str, int]:
        """Take back the last move (the move still counts as made)."""
        self._must_be_playing()
        if not self.history:
            raise GameError("Nothing to undo yet.", 422)
        last = self.history.pop()
        self.pegs[last["to"]].pop()
        self.pegs[last["from"]].append(last["disk"])
        self.undos += 1
        return last

    def hint(self) -> Dict[str, object]:
        self._must_be_playing()
        hint = full_hint(self.pegs)
        self.hints_used += 1
        return hint  # never None here: an unsolved puzzle always has a next move

    def solve_for_player(self) -> List[Dict[str, int]]:
        """Let the robot finish the puzzle. Returns the moves it made."""
        self._must_be_playing()
        self.assisted = True
        made: List[Dict[str, int]] = []
        while not self.solved:
            m = next_move(self.pegs)
            made.append(self.apply_move(m["from"], m["to"]))
        return made

    def restart(self) -> None:
        """Start over with the same number of disks (the game id stays)."""
        keep_id = self.id
        self.__init__(self.disks)
        self.id = keep_id

    # ---- scoring and reporting ----------------------------------------
    @property
    def elapsed_s(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.finished_at if self.finished_at is not None else time.time()
        return round(end - self.started_at, 1)

    def stars(self) -> Optional[int]:
        """3 = perfect and no hints, 2 = close to perfect, 1 = solved. None if not solved by the player."""
        if not self.solved or self.assisted:
            return None
        best = min_moves(self.disks)
        if self.moves_made == best:
            stars = 3
        elif self.moves_made <= best * 1.5:
            stars = 2
        else:
            stars = 1
        if self.hints_used > 0:
            stars = max(1, stars - 1)
        return stars

    def snapshot(self) -> Dict[str, object]:
        return {
            "game_id": self.id,
            "disks": self.disks,
            "pegs": [list(p) for p in self.pegs],
            "moves": self.moves_made,
            "min_moves": min_moves(self.disks),
            "moves_remaining": moves_remaining(self.pegs),
            "hints_used": self.hints_used,
            "undos": self.undos,
            "mistakes": self.invalid_attempts,
            "solved": self.solved,
            "assisted": self.assisted,
            "stars": self.stars(),
            "elapsed_s": self.elapsed_s,
            "can_undo": bool(self.history) and not self.solved,
            "history": list(self.history),
        }
