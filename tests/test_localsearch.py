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
    cost,
    generate_neighbours,
    hill_climbing,
    random_restarting_hillclimbing,
    simulated_annealing
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


# Test that alternative schedules are generated
def test_generate_neighbours():
    state = [36, 40, 0, 4]

    neighbours = generate_neighbours(PROBLEM, state)

    assert len(neighbours) > 0
    assert state not in neighbours


# Test that only one appliance changes in each neighbour
def test_one_appliance_changes():
    state = [36, 40, 0, 4]

    neighbours = generate_neighbours(PROBLEM, state)

    for neighbour in neighbours:
        changes = 0

        for i in range(len(state)):
            if state[i] != neighbour[i]:
                changes += 1

        assert changes == 1


# Test that neighbouring schedules stay within appliance time windows
def test_neighbour_domains():
    state = [36, 40, 0, 4]

    neighbours = generate_neighbours(PROBLEM, state)

    for neighbour in neighbours:
        assert len(neighbour) == len(state)

        for i in range(len(neighbour)):
            assert neighbour[i] in PROBLEM["domains"][i]


# Test that generating neighbours does not change the original schedule
def test_original_state_unchanged():
    state = [36, 40, 0, 4]
    original = list(state)

    generate_neighbours(PROBLEM, state)

    assert state == original


# Test that the correct number of neighbours is generated
def test_neighbour_count():
    state = [36, 40, 0, 4]

    neighbours = generate_neighbours(PROBLEM, state)

    expected = 0

    for domain in PROBLEM["domains"]:
        expected += len(domain) - 1

    assert len(neighbours) == expected


# Test that hill climbing improves or maintains the original cost
def test_hill_climbing_cost():
    state = [36, 40, 0, 4]

    original_cost = cost(PROBLEM, state)

    result = hill_climbing(PROBLEM, state)
    final_cost = cost(PROBLEM, result)

    assert final_cost <= original_cost


# Test that no cheaper neighbouring schedule remains
def test_hill_climbing_local_minimum():
    state = [36, 40, 0, 4]

    result = hill_climbing(PROBLEM, state)
    final_cost = cost(PROBLEM, result)

    neighbours = generate_neighbours(PROBLEM, result)

    for neighbour in neighbours:
        assert cost(PROBLEM, neighbour) >= final_cost


# Test that hill climbing does not change the original schedule
def test_hill_climbing_original_state():
    state = [36, 40, 0, 4]
    original = list(state)

    hill_climbing(PROBLEM, state)

    assert state == original


# Test that random-restart hill climbing returns a complete schedule
def test_random_restart_schedule():
    random.seed(42)

    result = random_restarting_hillclimbing(PROBLEM, restarts=5)

    assert result is not None
    assert len(result) == len(PROBLEM["names"])

    for i in range(len(result)):
        assert result[i] in PROBLEM["domains"][i]


# Test that multiple restarts perform at least as well as one restart
def test_random_restart_cost():
    random.seed(42)
    single = random_restarting_hillclimbing(PROBLEM, restarts=1)

    random.seed(42)
    multiple = random_restarting_hillclimbing(PROBLEM, restarts=5)

    assert cost(PROBLEM, multiple) <= cost(PROBLEM, single)


# Test that hill climbing does not change the original schedule
def test_hill_climbing_original_state():
    state = [36, 40, 0, 4]
    original = list(state)

    hill_climbing(PROBLEM, state)

    assert state == original


# Test that random-restart hill climbing returns a complete schedule
def test_random_restart_schedule():
    random.seed(42)

    result = random_restarting_hillclimbing(PROBLEM, restarts=5)

    assert result is not None
    assert len(result) == len(PROBLEM["names"])

    for i in range(len(result)):
        assert result[i] in PROBLEM["domains"][i]


# Test that multiple restarts perform at least as well as one restart
def test_random_restart_cost():
    random.seed(42)
    single = random_restarting_hillclimbing(PROBLEM, restarts=1)

    random.seed(42)
    multiple = random_restarting_hillclimbing(PROBLEM, restarts=5)

    assert cost(PROBLEM, multiple) <= cost(PROBLEM, single)



if __name__ == "__main__":
    tests = [test for name, test in sorted (globals().items()) 
            if name.startswith("test_")]

    for test in tests:
        test()
        print("PASS", test.__name__)

    print(len(tests), "tests passed")

    

