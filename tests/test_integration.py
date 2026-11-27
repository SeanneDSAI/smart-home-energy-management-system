"""
Integration tests for the Smart Home Energy Management System.

Run from the repository root:
    python tests/test_integration.py
"""

import os
import sys
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.knowledge_base import load_knowledge_base
from src.csp import make_problem, backtracking_search, is_valid
from src.localsearch import cost, random_restarting_hillclimbing
from src.controller import run_day
from src.visualisation import day_data

SCENARIOS = [
    "example",
    "no_solar_battery",
    "high_solar",
    "restricted_supply"
]


# Load a scenario from its folder
def load_scenario(name):
    folder = os.path.join(ROOT, "data", "scenarios", name)

    return load_knowledge_base(folder)


# Test that every scenario can create a scheduling problem
def test_all_scenarios_load():
    for name in SCENARIOS:
        kb = load_scenario(name)
        problem = make_problem(kb)

        assert len(problem["names"]) == 4
        assert len(problem["domains"]) == 4
        assert len(problem["background"]) == 48

        for domain in problem["domains"]:
            assert len(domain) > 0


# Test that CSP finds a valid schedule for every scenario
def test_csp_all_scenarios():
    for name in SCENARIOS:
        kb = load_scenario(name)
        problem = make_problem(kb)

        schedules, nodes = backtracking_search(problem)

        assert len(schedules) == 1
        assert len(schedules[0]) == len(problem["names"])
        assert is_valid(problem, schedules[0])


# Test that local search returns complete schedules across all scenarios
def test_local_search_all_scenarios():
    for name in SCENARIOS:
        kb = load_scenario(name)
        problem = make_problem(kb)

        random.seed(42)

        schedule = random_restarting_hillclimbing(
            problem, restarts=20
        )

        assert schedule is not None
        assert len(schedule) == len(problem["names"])

        for i in range(len(schedule)):
            assert schedule[i] in problem["domains"][i]

        assert cost(problem, schedule) >= 0


# Test that the controller works across different households
def test_controller_all_scenarios():
    for name in SCENARIOS:
        kb = load_scenario(name)

        results = run_day(kb)

        assert len(results) == 48

        if "battery" in kb["graph"]:
            battery = kb["graph"]["battery"]

            for row in results:
                assert battery["min_charge_kwh"] <= row["soc_kwh"]
                assert row["soc_kwh"] <= battery["capacity_kwh"]

        else:
            for row in results:
                assert row["battery_action"] is None
                assert row["soc_kwh"] == 0


# Test that valid schedules can be used by the visualisation module
def test_visualisation_integration():
    for name in SCENARIOS:
        kb = load_scenario(name)
        problem = make_problem(kb)

        schedules, nodes = backtracking_search(problem)

        assert len(schedules) > 0

        schedule = schedules[0]

        problem, sources, rows = day_data(kb, schedule)

        assert len(rows) == 48

        for row in rows:
            assert row["grid_import_kw"] >= 0

            assert row["grid_import_kw"] <= problem["supply_limit"] + 1e-9


if __name__ == "__main__":
    tests = [test for name, test in sorted(globals().items())
             if name.startswith("test_")]

    for test in tests:
        test()
        print("PASS", test.__name__)

    print(len(tests), "tests passed")