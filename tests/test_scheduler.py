"""
Tests for src/scheduler.py: running every algorithm on a scenario and picking
the best schedule.
Run from the repository root:
    pytest tests/test_scheduler.py
"""

import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.knowledge_base import load_knowledge_base                 # noqa: E402
from src.csp import make_problem, is_valid                         # noqa: E402
from src.scheduler import (solve_all, schedule_costs, best_schedule,  # noqa: E402
                           BASELINE)

PROBLEM = make_problem(load_knowledge_base(os.path.join(ROOT, "data", "scenarios", "example")))


def test_solve_all_baseline_first():
    random.seed(1)
    schedules = solve_all(PROBLEM)
    assert list(schedules) == [BASELINE, "Random-restart hill climbing", "Simulated annealing"]
    assert schedules[BASELINE] == [d[0] for d in PROBLEM["domains"]]


def test_solve_all_schedules_are_valid():
    random.seed(1)
    for schedule in solve_all(PROBLEM).values():
        assert is_valid(PROBLEM, schedule)


def test_searches_beat_the_baseline():
    random.seed(1)
    costs = schedule_costs(PROBLEM, solve_all(PROBLEM))
    assert costs[best_schedule(costs)] < costs[BASELINE]


def test_best_schedule_skips_baseline():
    # even when the baseline is cheapest, a search result is picked
    assert best_schedule({"baseline": 1.0, "a": 5.0, "b": 3.0}) == "b"
