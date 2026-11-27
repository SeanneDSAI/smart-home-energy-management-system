"""
Unit tests for src/localsearch.py.
Run from the repository root:
    python tests/test_localsearch.py
"""

import os
import sys
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.knowledge_base import load_knowledge_base
from src.csp import make_problem
from src.localsearch import (
    random_state,
    cost
)

# Load the example household scenario
KB = load_knowledge_base(os.path.join(ROOT, "data", "scenarios", "example"))

# Create the scheduling problem
PROBLEM = make_problem(KB)


# Test that every appliance is assigned a starting slot
def test_random_state_length():
    state = random_state(PROBLEM)

    assert len(state) == len(PROBLEM["names"])


# Test that randomly generated start times belong to each appliance's domain
def test_random_state_domains():
    state = random_state(PROBLEM)

    for i in range(len(state)):
        assert state[i] in PROBLEM["domains"][i]


# Test that multiple random schedules stay with their domains
def test_multiple_random_states():
    random.seed(42)

    for _ in range(20):
        state = random_state(PROBLEM)

    assert len(state) == len(PROBLEM["names"])

    for i in range(len(state)):
        assert state[i] in PROBLEM["domains"][i]


# Test that electricity cost is calculated correctly 
def test_electricity_cost():
    problem = make_problem(KB)

    problem["background"] = [1.0] * 48
    problem["solar"] = [0.0] * 48
    problem["price"] = [0.20] * 48
    problem["carbon"] = [0.0] * 48

    result = cost(problem, [])

    assert abs(result - 4.8) < 1e-9


# Test that carbon emmisions included in the cost 
def test_carbon_cost():
    problem = make_problem(KB)

    problem["background"] = [1.0] * 48
    problem["solar"] = [0.0] * 48
    problem["price"] = [0.0] * 48
    problem["carbon"] = [200.0] * 48

    result = cost(problem, [])

    assert abs(result - 0.3984) < 1e-9


# Test that solar generation reduces the cost
def test_solar_reduces_cost():
    problem = make_problem(KB)

    problem["background"] = [1.0] * 48
    problem["solar"] = [0.0] * 48
    problem["price"] = [0.20] * 48
    problem["carbon"] = [0.0] * 48

    without_solar = cost(problem, [])

    problem["solar"] = [0.5] * 48

    with_solar = cost(problem, [])

    assert with_solar < without_solar
    assert abs(with_solar - 2.4) < 1e-9
    

# Test that running a noisy appliance during quiet hours adds a penalty
def test_quiet_hours_penalty():
    problem = make_problem(KB)

    problem["price"] = [0.0] * 48
    problem["carbon"] = [0.0] * 48

    valid = [36, 40, 0, 4]
    invalid = [46, 40, 0, 4]

    valid_cost = cost(problem, valid)
    invalid_cost = cost(problem, invalid)

    assert valid_cost == 0
    assert invalid_cost == 30


# Test that exceeding the supply limit adds a penalty 
def test_supply_limit_penalty():
    problem = make_problem(KB)

    problem["background"] = [6.0] * 48
    problem["solar"] = [0.0] * 48
    problem["price"] = [0.0] * 48
    problem["carbon"] = [0.0] * 48
    problem["supply_limit"] = 5.0 

    result = cost(problem, [])

    assert abs(result - 480.0) < 1e-9


if __name__ == "__main__":
    tests = [test for name, test in sorted (globals().items()) 
            if name.startswith("test_")]

    for test in tests:
        test()
        print("PASS", test.__name__)

    print(len(tests), "tests passed")

    

