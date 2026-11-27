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
    supply_ok,
    is_valid,
    node_consistent_domains,
    select_variable,
    forward_check,
    backtracking_search,
    schedule_to_times 
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


def test_valid_schedule():
    schedule = [36, 40, 0, 4]

    assert is_valid(PROBLEM, schedule) == True


# Test that a schedule breaking an appliance deadline is rejected
def test_invalid_deadline():
    schedule = [36, 40, 13, 4]

    assert is_valid(PROBLEM, schedule) == False


# Test that a noisy appliance running during quiet hours is rejected
def test_invalid_quiet_hours():
    schedule = [46, 40, 0, 4]

    assert is_valid(PROBLEM, schedule) == False


# Test that invalid start times are removed from the domains 
def test_node_consistent_domains():
    domains = node_consistent_domains(PROBLEM)

    i = PROBLEM["names"].index("washing_machine")
    j = PROBLEM["names"].index("dishwasher")

    assert domains[i] == list(range(36, 44))
    assert domains[j] == [40, 41, 42]


# Test that node consistency does not change the original domains
def test_original_domains_unchanged():
    original = [list(domain) for domain in PROBLEM["domains"]]

    node_consistent_domains(PROBLEM)

    assert PROBLEM["domains"] == original


# Test that MRV selects the appliance with the fewest available slots
def test_mrv_selection():
    domains = node_consistent_domains(PROBLEM)

    selected = select_variable(domains, {}, True)

    i = PROBLEM["names"].index("dishwasher")

    assert selected == i


# Test variable selection when MRV is disabled 
def test_selection_without_mrv():
    domains = node_consistent_domains(PROBLEM)

    selected = select_variable(domains, {}, False)

    assert selected == 0 


# Test that MRV does not select an appliance already assigned 
def test_mrv_skips_assigned():
    domains = node_consistent_domains(PROBLEM)

    i = PROBLEM["names"].index("dishwasher")
    assignment = {i: 40}

    selected = select_variable(domains, assignment, True)

    assert selected != 1
    assert selected == PROBLEM["names"].index("washing_machine")


# Test that forward checking removes conflicting start times 
def test_forward_check():
    problem = make_problem(KB)
    problem["supply_limit"] = 8.0

    domains = node_consistent_domains(problem)

    i = problem["names"].index("ev_charger")
    j = problem["names"].index("immersion_heater")

    assignment = {i: 0}

    new_domains = forward_check(problem, domains, assignment)

    assert new_domains is not None 
    assert 0 not in new_domains[j]
    assert 5 not in new_domains[j]
    assert 6 in new_domains[j]


# Test that forward checking detects when no valid starts remain
def test_forward_check_dead_end():
    problem = make_problem(KB)
    problem["supply_limit"] = 8.0

    domains = node_consistent_domains(problem)

    i = problem["names"].index("ev_charger")
    j = problem["names"].index("immersion_heater")

    domains[j] = [0]

    assignment = {i: 0}

    assert forward_check(problem, domains, assignment) is None


# Test that backtracking finds a complete and valid schedule
def test_backtracking_valid_schedule():
        schedules, nodes = backtracking_search(PROBLEM)

        assert len(schedules) == 1
        assert len(schedules[0]) == len(PROBLEM["names"])        
        assert is_valid(PROBLEM, schedules[0])
        assert nodes > 0


# Test that backtracking can find multiple valid schedules 
def test_backtracking_multiple_schedules():
    schedules, nodes = backtracking_search(PROBLEM, limit=5)

    assert len(schedules) == 5

    for schedule in schedules:
        assert len(schedule) == len(PROBLEM["names"])
        assert is_valid(PROBLEM, schedule)


# Test that backtracking works without MRV and forward checking
def test_backtracking_without_heuristics():
    schedules, nodes = backtracking_search(
        PROBLEM,
        use_mrv=False,
        use_forward_checking=False
    )

    assert len(schedules) == 1
    assert len(schedules[0]) == len(PROBLEM["names"])
    assert is_valid(PROBLEM, schedules[0])
    assert nodes > 0


# Test that no schedule is returned when the supply limit is too low 
def test_impossible_schedule():
    problem = make_problem(KB)

    problem["supply_limit"] = 5.0 
    problem["solar"] = [0] * 48
    schedules, nodes = backtracking_search(problem)

    assert schedules == []


# Test that backtracking detects an appliance with no available start times
def test_empty_domain():
    problem = make_problem(KB)

    i = problem["names"].index("washing_machine")
    problem["domains"][i] = []

    schedules, nodes = backtracking_search(problem)

    assert schedules == []
    assert nodes == 0


# Test that appliance schedules convert to the correct start and finish times
def test_schedule_to_times():
    schedule = [36, 40, 0, 4]

    times = schedule_to_times(PROBLEM, schedule)

    assert times["washing_machine"] == ("18:00", "19:30")
    assert times["dishwasher"] == ("20:00", "22:00")
    assert times["immersion_heater"] == ("00:00", "01:00")
    assert times["ev_charger"] == ("02:00", "05:00")


# Test that appliance finish times wrap around midnight
def test_schedule_to_times_midnight():
    schedule = [36, 40, 0, 46]

    times = schedule_to_times(PROBLEM, schedule)

    assert times["ev_charger"] == ("23:00", "02:00")


# Test that every flexible appliance is included in the converted schedule
def test_schedule_to_times_all_appliances():
    schedule = [36, 40, 0, 4]

    times = schedule_to_times(PROBLEM, schedule)

    assert len(times) == len(PROBLEM["names"])

    for name in PROBLEM["names"]:
        assert name in times


if __name__ == "__main__":
    tests = [test for name, test in sorted(globals().items())
             if name.startswith("test_")]

    for test in tests:
        test()
        print("PASS", test.__name__)

    print(len(tests), "tests passed")
