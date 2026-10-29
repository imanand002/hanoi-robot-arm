"""Tests for the game: rules, hints, scoring.
The big test checks the hint engine against a brute-force search (BFS)
over EVERY possible position, so "hint = best move" is proven, not hoped.
"""

import itertools
import random
from collections import deque

import pytest

from backend.game import Game, GameError
from backend.hints import moves_remaining, next_move
from backend.service import ServiceError, game_hint, game_move, game_new, game_restart, game_solve, game_undo
from backend.validator import check_move


def pegs_from_positions(pos):
    pegs = [[], [], []]
    for disk in range(len(pos), 0, -1):          # biggest first
        pegs[pos[disk - 1]].append(disk)
    return pegs


def apply(pegs, move):
    new = [list(p) for p in pegs]
    new[move["to"]].append(new[move["from"]].pop())
    return new


def bfs_distances(n):
    """Shortest number of moves to reach 'all on C' from every position."""
    def neighbours(pos):
        pegs = pegs_from_positions(pos)
        for s in range(3):
            for t in range(3):
                if check_move(pegs, s, t) is None:
                    d = pegs[s][-1]
                    new = list(pos)
                    new[d - 1] = t
                    yield tuple(new)

    goal = tuple([2] * n)
    dist = {goal: 0}
    queue = deque([goal])
    while queue:
        cur = queue.popleft()
        for nxt in neighbours(cur):          # moves are reversible, so this works backwards too
            if nxt not in dist:
                dist[nxt] = dist[cur] + 1
                queue.append(nxt)
    return dist


@pytest.mark.parametrize("n", range(1, 7))
def test_hints_are_optimal_from_every_position(n):
    dist = bfs_distances(n)
    assert len(dist) == 3**n
    for pos, best in dist.items():
        pegs = pegs_from_positions(pos)
        assert moves_remaining(pegs) == best
        move = next_move(pegs)
        if best == 0:
            assert move is None
        else:
            assert check_move(pegs, move["from"], move["to"]) is None
            assert pegs[move["from"]][-1] == move["disk"]
            assert dist[tuple(apply_pos(pos, move))] == best - 1


def apply_pos(pos, move):
    new = list(pos)
    new[move["disk"] - 1] = move["to"]
    return new


def test_check_move_messages():
    pegs = [[3, 2], [1], []]
    assert check_move(pegs, 0, 2) is None
    assert "bigger than disk 1" in check_move(pegs, 0, 1)
    assert "empty" in check_move(pegs, 2, 0)
    assert "different rods" in check_move(pegs, 1, 1)
    assert "Rods are A, B and C" in check_move(pegs, 0, 7)


def test_player_can_win_by_following_hints_after_random_mistakes():
    rng = random.Random(7)
    for n in (3, 4, 5, 6):
        game = Game(n)
        for _ in range(25):                       # wander around randomly first
            s, t = rng.randrange(3), rng.randrange(3)
            try:
                game.apply_move(s, t)
            except GameError:
                pass
        if game.solved:
            continue
        expected = moves_remaining(game.pegs)
        followed = 0
        while not game.solved:
            h = game.hint()
            game.apply_move(h["from"], h["to"])
            followed += 1
        assert followed == expected


def test_illegal_move_is_refused_and_counted():
    game = Game(3)
    with pytest.raises(GameError, match="empty"):
        game.apply_move(1, 2)
    game.apply_move(0, 1)                         # disk 1 -> B
    with pytest.raises(GameError, match="bigger than disk 1"):
        game.apply_move(0, 1)                     # disk 2 onto disk 1
    assert game.invalid_attempts == 2
    assert game.pegs == [[3, 2], [1], []]         # board unchanged by illegal moves


def test_undo_and_move_counter():
    game = Game(3)
    game.apply_move(0, 2)
    game.undo()
    assert game.pegs == [[3, 2, 1], [], []]
    assert game.moves_made == 1 and game.undos == 1
    with pytest.raises(GameError, match="Nothing to undo"):
        game.undo()


def test_stars():
    perfect = Game(3)
    for h in range(7):
        m = next_move(perfect.pegs)
        perfect.apply_move(m["from"], m["to"])
    assert perfect.solved and perfect.stars() == 3

    hinted = Game(3)
    while not hinted.solved:
        h = hinted.hint()
        hinted.apply_move(h["from"], h["to"])
    assert hinted.stars() == 2                    # perfect moves, but hints were used

    sloppy = Game(2)
    for s, t in [(0, 1), (1, 0), (0, 1), (1, 0), (0, 1), (1, 0), (0, 1), (1, 0)]:
        sloppy.apply_move(s, t)
    for s, t in [(0, 1), (0, 2), (1, 2)]:
        sloppy.apply_move(s, t)
    assert sloppy.solved and sloppy.stars() == 1

    robot = Game(3)
    robot.solve_for_player()
    assert robot.solved and robot.assisted and robot.stars() is None


def test_no_moves_after_solved():
    game = Game(1)
    game.apply_move(0, 2)
    assert game.solved
    for action in (lambda: game.apply_move(2, 0), game.undo, game.hint, game.solve_for_player):
        with pytest.raises(GameError, match="already solved"):
            action()


def test_service_flow():
    snap = game_new(3)
    gid = snap["game_id"]
    assert snap["moves_remaining"] == 7 and snap["min_moves"] == 7
    hint = game_hint(gid)
    assert hint["hint"]["disk"] == 1 and hint["hint"]["to"] == 2 and hint["game"]["hints_used"] == 1
    res = game_move(gid, hint["hint"]["from"], hint["hint"]["to"])
    assert res["game"]["moves_remaining"] == 6
    with pytest.raises(ServiceError) as err:
        game_move(gid, 0, 2)                      # disk 2 onto disk 1 is illegal
    assert err.value.status_code == 422
    assert game_undo(gid)["game"]["pegs"] == [[3, 2, 1], [], []]
    solved = game_solve(gid)
    assert solved["game"]["solved"] and len(solved["moves"]) == 7
    assert game_restart(gid)["pegs"] == [[3, 2, 1], [], []]
    with pytest.raises(ServiceError) as err:
        game_move("nope", 0, 1)
    assert err.value.status_code == 404
    with pytest.raises(ServiceError):
        game_new(0)
