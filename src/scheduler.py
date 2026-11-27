"""
Scheduler: runs the search algorithms on a scenario and picks the best schedule.

Sits on top of src.localsearch. It runs a simple baseline and both search
algorithms, scores every schedule with the same cost function, and picks the
winner. The menu (main_cli.py) and the charts (src.visualisation) both use it,
so they always agree on which schedule is best.

A schedule is a list of start slots, one per flexible appliance, in the order
of problem["names"] (see src.csp.make_problem).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.localsearch import (random_state, cost, random_restarting_hillclimbing,
                             simulated_annealing)

BASELINE = "Run as early as possible"


def solve_all(problem):
    """{name: schedule} for the baseline (every appliance at its earliest start)
    followed by both search algorithms. The baseline is always the first entry."""
    return {
        BASELINE: [d[0] for d in problem["domains"]],
        "Hill climbing": random_restarting_hillclimbing(problem),
        "Simulated annealing": simulated_annealing(problem, random_state(problem)),
    }


def schedule_costs(problem, schedules):
    """{schedule name: cost score}."""
    return {name: cost(problem, schedule) for name, schedule in schedules.items()}


def best_schedule(costs):
    """Name of the cheapest schedule in costs, leaving out the baseline (the
    first entry) unless it is the only one."""
    candidates = list(costs)[1:] or list(costs)
    return min(candidates, key=costs.get)
