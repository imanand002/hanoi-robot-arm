"""Tests for the algorithms, the referee and the service layer.
Run with:  pytest -q
"""

import pytest

from backend.algorithms import min_moves, run_algorithm, solve_iterative, solve_recursive
from backend.service import ServiceError, compare, reset_simulation, start_simulation, validate_given_moves
from backend.validator import InvalidMoveError, validate_moves, validate_solution


@pytest.mark.parametrize("n", range(1, 13))
def test_both_algorithms_are_optimal_and_valid(n):
    for solver in (solve_recursive, solve_iterative):
        moves = solver(n)
        assert len(moves) == 2**n - 1
        validate_solution(n, moves)


@pytest.mark.parametrize("n", range(1, 11))
def test_algorithms_give_same_moves(n):
    assert solve_recursive(n) == solve_iterative(n)


def test_min_moves_formula():
    assert [min_moves(n) for n in (1, 2, 3, 10)] == [1, 3, 7, 1023]


def test_run_algorithm_reports_time_and_minimum():
    result = run_algorithm("recursive", 5)
    assert result["total_moves"] == 31 and result["is_minimum"]
    assert result["execution_time_ms"] >= 0


def test_unknown_algorithm_is_rejected():
    with pytest.raises(ValueError):
        run_algorithm("magic", 3)


def test_validator_catches_big_on_small():
    # disk 1 -> B, then disk 3 -> B would sit on a smaller disk
    with pytest.raises(InvalidMoveError, match="cannot put disk"):
        validate_moves(3, [{"disk": 1, "from": 0, "to": 1}, {"disk": 2, "from": 0, "to": 1}])


def test_validator_catches_wrong_top_disk_and_empty_peg():
    with pytest.raises(InvalidMoveError, match="not on top"):
        validate_moves(3, [{"disk": 3, "from": 0, "to": 2}])
    with pytest.raises(InvalidMoveError, match="empty"):
        validate_moves(3, [{"disk": 1, "from": 1, "to": 2}])


def test_validator_catches_unfinished_puzzle():
    with pytest.raises(InvalidMoveError, match="not solved"):
        validate_solution(3, [{"disk": 1, "from": 0, "to": 2}])


def test_start_and_reset_simulation():
    sim = start_simulation(4, "iterative")
    assert sim["validated"] and sim["total_moves"] == 15 and sim["min_moves"] == 15
    reset = reset_simulation(sim["simulation_id"])
    assert reset["pegs"] == [[4, 3, 2, 1], [], []]


def test_service_errors():
    with pytest.raises(ServiceError):
        start_simulation(0, "recursive")
    with pytest.raises(ServiceError):
        start_simulation(11, "recursive")
    with pytest.raises(ServiceError):
        start_simulation(3, "nope")
    with pytest.raises(ServiceError) as err:
        reset_simulation("does-not-exist")
    assert err.value.status_code == 404


def test_compare_returns_both_algorithms():
    result = compare(8, repeats=2)
    assert set(result["results"]) == {"recursive", "iterative"}
    assert result["same_moves"] is True and result["min_moves"] == 255


def test_validate_endpoint_logic():
    assert validate_given_moves(1, [{"disk": 1, "from": 0, "to": 2}])["valid"]
    assert not validate_given_moves(2, [{"disk": 2, "from": 0, "to": 2}])["valid"]
