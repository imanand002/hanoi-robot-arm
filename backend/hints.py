"""
hints.py  --  The "coach" that knows the best next move from ANY position.

The player may wander away from the textbook solution, so we cannot just
replay a stored list of moves. Instead we look at where every disk is NOW
and ask: "what is the best next move to finish at rod C?"

The idea (say it out loud, it is easy):
  * Find the BIGGEST disk that is not on the goal rod yet. Call it k.
  * To move k to the goal, every smaller disk must first be out of the way,
    on the third rod (neither where k is, nor the goal).
  * So the best next move is the first move of "get disks 1..k-1 onto that
    third rod". If they are already there, move disk k itself.
This never wastes a move, so following hints always gives the shortest finish.
"""

from typing import Dict, List, Optional, Sequence

from .algorithms import PEG_NAMES

GOAL = 2  # rod C


def _positions(pegs: Sequence[Sequence[int]]) -> Dict[int, int]:
    """Which rod is each disk on?  {disk_number: rod_number}"""
    return {disk: rod for rod, stack in enumerate(pegs) for disk in stack}


def biggest_not_home(pegs: Sequence[Sequence[int]], goal: int = GOAL) -> int:
    """Largest disk that is not yet on the goal rod (0 if the puzzle is solved)."""
    pos = _positions(pegs)
    for disk in range(len(pos), 0, -1):
        if pos[disk] != goal:
            return disk
    return 0


def next_move(pegs: Sequence[Sequence[int]], goal: int = GOAL) -> Optional[Dict[str, int]]:
    """The best next move as {"disk", "from", "to"}, or None if already solved."""
    pos = _positions(pegs)

    def helper(k: int, target: int) -> Optional[Dict[str, int]]:
        while k >= 1 and pos[k] == target:   # already in place, ignore it
            k -= 1
        if k == 0:
            return None
        source = pos[k]
        spare = 3 - source - target          # the third rod (0+1+2 = 3)
        first = helper(k - 1, spare)         # first clear the smaller disks
        if first is not None:
            return first
        return {"disk": k, "from": source, "to": target}

    return helper(len(pos), goal)


def moves_remaining(pegs: Sequence[Sequence[int]], goal: int = GOAL) -> int:
    """The fewest moves still needed to finish from this position."""
    pos = _positions(pegs)

    def count(k: int, target: int) -> int:
        while k >= 1 and pos[k] == target:
            k -= 1
        if k == 0:
            return 0
        spare = 3 - pos[k] - target
        # clear smaller disks, move disk k (1 move), then bring the 2^(k-1)-1
        # smaller disks on top of it  ->  count(...) + 2^(k-1)
        return count(k - 1, spare) + 2 ** (k - 1)

    return count(len(pos), goal)


def explain(pegs: Sequence[Sequence[int]], move: Dict[str, int]) -> str:
    """Turn a hint move into a short, friendly sentence."""
    disk, src, dst = move["disk"], PEG_NAMES[move["from"]], PEG_NAMES[move["to"]]
    big = biggest_not_home(pegs)
    text = f"Move disk {disk} from rod {src} to rod {dst}."
    if disk == big:
        return text + f" The way is clear, so the biggest unfinished disk ({disk}) can go home to rod C!"
    return text + f" This clears the way so disk {big} (the biggest disk not on rod C yet) can reach rod C."


def full_hint(pegs: Sequence[Sequence[int]]) -> Optional[Dict[str, object]]:
    move = next_move(pegs)
    if move is None:
        return None
    return {
        **move,
        "from_name": PEG_NAMES[move["from"]],
        "to_name": PEG_NAMES[move["to"]],
        "message": explain(pegs, move),
    }
