"""
Unit tests for src/csp.py
Run from the repository root:
    python tests/test_csp.py
"""

import os 
import sys 

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.knowledge_base import load_knowledge_base
from src.csp import (
    time_slots, 
    start_times, 
    make_problem,
    running_slots,
    quiet_ok,
    load_per_slot,
    supply_ok
)

# Load the example household scenario
KB = load_knowledge_base(os.path.join(ROOT, "data", "scenarios", "example"))

# Create the CSP problem
PROBLEM = make_problem(KB)

# Test that slot numbers convert to the correct times
def test_time_slots():
    assert time_slots(0) == "00:00"
    assert time_slots(15) == "07:30"
    assert time_slots(47) == "23:30"
    assert time_slots(48) == "00:00"


# Test the earliest and the latest possible start times 
def test_start_times():
    starts = start_times(KB, "immersion_heater")

    assert starts[0] == 0
    assert starts[-1] == 12
    assert len(starts) == 13


# Test start time for an appliance that can run past midnight
def test_start_times_midnight():
    starts = start_times(KB, "ev_charger")

    assert starts[0] == 38
    assert starts[-1] == 9
    assert 0 in starts 
    assert len (starts) == 20


# Test that an appliance runs for the correct number of slots 
def test_running_slots():
    i = PROBLEM["names"].index("washing_machine")

    slots = running_slots(PROBLEM, i, 36)

    assert slots == [36, 37, 38]


# Test that appliance running slots wrap around midnight
def test_running_slots_midnight():
    i = PROBLEM["names"].index("ev_charger")

    slots = running_slots(PROBLEM, i, 46)

    assert slots == [46, 47, 0, 1, 2, 3]


# Test that noisy appliances respect quiet hours
def test_quiet_hours_noisy_appliances():
    i = PROBLEM["names"].index("washing_machine")

    assert quiet_ok(PROBLEM, i, 36) == True 
    assert quiet_ok(PROBLEM, i, 46) == False 
    assert quiet_ok(PROBLEM, i, 44) == False


# Test that non-noisy appliances can run during quiet hours
def test_quiet_hours_non_noisy_appliance():
    i = PROBLEM["names"].index("ev_charger")

    assert quiet_ok(PROBLEM, i, 46) == True
    assert quiet_ok(PROBLEM, i, 0) == True

# Test electricity demand without any flexible appliances running
def test_background_load():
    load = load_per_slot(PROBLEM, {})

    assert len(load) == 48  
    assert load == PROBLEM["background"]


# Test that appliance power is added to the background load 
def test_appliance_load():
    i = PROBLEM["names"].index("washing_machine")

    assignment = {i: 36}
    load = load_per_slot(PROBLEM, assignment)

    assert abs(load[36] - 5.3) < 1e-9
    assert abs(load[37] - 5.3) < 1e-9
    assert abs(load[38] - 2.7) < 1e-9


# Test that deand below the supply limit is accepted
def test_supply_limit_valid():
    i = PROBLEM["names"].index("ev_charger")

    assignment = {i: 0}

    assert supply_ok(PROBLEM, assignment) == True


# Test that excessive electricity demand is rejected 
def test_supply_limit_exceeded():
    assignment = {}

    for i in range(len(PROBLEM["names"])):
        assignment[i] = 0

    assert supply_ok(PROBLEM, assignment) == False


# Test that solar generation reduces grid demand
def test_solar_reduces_grid_demand():
    problem = make_problem(KB)

    i = problem["names"].index("ev_charger")
    problem["supply_limit"] = 5.0

    assignment = {i: 24}

    assert supply_ok(problem, assignment) == True


if __name__ == "__main__":
    tests = [test for name, test in sorted(globals().items())
             if name.startswith("test_")]

    for test in tests:
        test()
        print("PASS", test.__name__)

    print(len(tests), "tests passed")
