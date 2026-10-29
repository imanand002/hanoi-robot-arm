"""
algorithms.py  --  The "brain" that knows how to solve Tower of Hanoi.

Think of three sticks (rods): 0 = A, 1 = B, 2 = C.
A pile of disks starts on stick A. We must move the whole pile to stick C.

Rules:
  1. Move only ONE disk at a time.
  2. Only take the TOP disk of a pile.
  3. Never put a big disk on top of a small disk.

Disk 1 is the smallest. Disk n is the biggest.

A "move" is a small dictionary:  {"disk": 3, "from": 0, "to": 2}
"""

import time
from typing import Callable, Dict, List

PEG_NAMES = ["A", "B", "C"]
SOURCE, SPARE, TARGET = 0, 1, 2

Move = Dict[str, int]


def min_moves(n: int) -> int:
    """The smallest possible number of moves for n disks is 2^n - 1."""
    return 2**n - 1


# ---------------------------------------------------------------------------
# 1) RECURSIVE  ("ask a smaller helper to do part of the job")
# ---------------------------------------------------------------------------
def solve_recursive(n: int) -> List[Move]:
    """
    To move k disks from s to t using helper h:
        a) move the top k-1 disks from s to h     (smaller problem!)
        b) move the biggest disk from s to t
        c) move the k-1 disks from h to t         (smaller problem again!)
    """
    moves: List[Move] = []

    def hanoi(k: int, s: int, t: int, h: int) -> None:
        if k == 0:  # nothing to move, stop asking for help
            return
        hanoi(k - 1, s, h, t)
        moves.append({"disk": k, "from": s, "to": t})
        hanoi(k - 1, h, t, s)

    hanoi(n, SOURCE, TARGET, SPARE)
    return moves


# ---------------------------------------------------------------------------
# 2) ITERATIVE  ("use a loop and a simple repeating pattern")
# ---------------------------------------------------------------------------
def solve_iterative(n: int) -> List[Move]:
    """
    Classic loop trick. Call the pegs x (source), y (target), z (spare).
    If n is EVEN, swap y and z. Then repeat for i = 1 .. 2^n - 1:
        i % 3 == 1 -> make the legal move between x and y
        i % 3 == 2 -> make the legal move between x and z
        i % 3 == 0 -> make the legal move between y and z
    "Legal move between two pegs" = move the smaller top disk onto the
    other peg (or move any disk onto an empty peg).
    """
    pegs: List[List[int]] = [list(range(n, 0, -1)), [], []]
    moves: List[Move] = []

    x, y, z = SOURCE, TARGET, SPARE
    if n % 2 == 0:
        y, z = z, y

    def legal_move(a: int, b: int) -> None:
        # Decide direction: which top disk is smaller?
        if not pegs[a]:
            src, dst = b, a
        elif not pegs[b]:
            src, dst = a, b
        elif pegs[a][-1] < pegs[b][-1]:
            src, dst = a, b
        else:
            src, dst = b, a
        disk = pegs[src].pop()
        pegs[dst].append(disk)
        moves.append({"disk": disk, "from": src, "to": dst})

    for i in range(1, min_moves(n) + 1):
        if i % 3 == 1:
            legal_move(x, y)
        elif i % 3 == 2:
            legal_move(x, z)
        else:
            legal_move(y, z)

    return moves


ALGORITHMS: Dict[str, Callable[[int], List[Move]]] = {
    "recursive": solve_recursive,
    "iterative": solve_iterative,
}


def run_algorithm(name: str, n: int) -> dict:
    """Run one algorithm, time it with a stopwatch, and report the results."""
    if name not in ALGORITHMS:
        raise ValueError(f"Unknown algorithm '{name}'. Choose: {', '.join(ALGORITHMS)}")

    start = time.perf_counter()  # start stopwatch
    moves = ALGORITHMS[name](n)
    elapsed_ms = (time.perf_counter() - start) * 1000  # stop stopwatch

    return {
        "algorithm": name,
        "disks": n,
        "moves": moves,
        "total_moves": len(moves),
        "min_moves": min_moves(n),
        "is_minimum": len(moves) == min_moves(n),
        "execution_time_ms": round(elapsed_ms, 4),
    }


def best_time_ms(name: str, n: int, repeats: int = 3) -> float:
    """Run several times and keep the fastest time (less noisy)."""
    return min(run_algorithm(name, n)["execution_time_ms"] for _ in range(max(1, repeats)))
