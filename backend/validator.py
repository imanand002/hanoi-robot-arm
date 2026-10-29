"""
validator.py  --  The "referee" that checks every move follows the rules.
"""

from typing import List, Sequence


class InvalidMoveError(ValueError):
    """Raised when a move breaks a Tower of Hanoi rule."""


def initial_pegs(n: int) -> List[List[int]]:
    """All disks on peg A, biggest at the bottom: [[n, ..., 2, 1], [], []]"""
    return [list(range(n, 0, -1)), [], []]


def validate_moves(n: int, moves: Sequence[dict]) -> List[List[int]]:
    """
    Replay all moves on a pretend board. Raise InvalidMoveError (with a
    friendly message) at the first mistake. Return the final board.
    """
    pegs = initial_pegs(n)

    for number, move in enumerate(moves, start=1):
        try:
            disk, src, dst = int(move["disk"]), int(move["from"]), int(move["to"])
        except (KeyError, TypeError, ValueError):
            raise InvalidMoveError(f"Move {number}: needs 'disk', 'from' and 'to' numbers.")

        if src not in (0, 1, 2) or dst not in (0, 1, 2):
            raise InvalidMoveError(f"Move {number}: pegs must be 0, 1 or 2.")
        if src == dst:
            raise InvalidMoveError(f"Move {number}: source and destination are the same peg.")
        if not pegs[src]:
            raise InvalidMoveError(f"Move {number}: peg {'ABC'[src]} is empty, nothing to pick up.")
        if pegs[src][-1] != disk:
            raise InvalidMoveError(
                f"Move {number}: disk {disk} is not on top of peg {'ABC'[src]} "
                f"(top is disk {pegs[src][-1]})."
            )
        if pegs[dst] and pegs[dst][-1] < disk:
            raise InvalidMoveError(
                f"Move {number}: cannot put disk {disk} on smaller disk {pegs[dst][-1]}."
            )

        pegs[dst].append(pegs[src].pop())

    return pegs


def validate_solution(n: int, moves: Sequence[dict]) -> None:
    """Moves must be legal AND must end with every disk on peg C."""
    final = validate_moves(n, moves)
    if final[2] != list(range(n, 0, -1)):
        raise InvalidMoveError("The moves are legal but the puzzle is not solved (all disks must end on C).")


def check_move(pegs: Sequence[Sequence[int]], src: int, dst: int):
    """
    Used by the GAME. Look at ONE move a player wants to make.
    Return None if it is allowed, otherwise a friendly message saying why not.
    """
    if src not in (0, 1, 2) or dst not in (0, 1, 2):
        return "Rods are A, B and C. Please pick one of them."
    if src == dst:
        return "Pick two different rods: the disk has to go to another rod."
    if not pegs[src]:
        return f"Rod {'ABC'[src]} is empty, so there is no disk to pick up."
    disk = pegs[src][-1]
    if pegs[dst] and pegs[dst][-1] < disk:
        return (
            f"Not allowed! Disk {disk} is bigger than disk {pegs[dst][-1]}, "
            f"so it cannot sit on top of it."
        )
    return None
