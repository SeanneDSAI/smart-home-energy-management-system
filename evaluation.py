"""
Evaluation of the Smart Home Energy Management System.

Compares CSP and local search algorithms across different
household scenarios.

Run from the repository root:
    python evaluation.py
"""

import os
import time
import random

from src.knowledge_base import load_knowledge_base

from src.csp import (
    make_problem,
    backtracking_search,
    is_valid,
    load_per_slot
)

from src.localsearch import (
    random_state,
    cost,
    hill_climbing,
    random_restarting_hillclimbing,
    simulated_annealing
)

ROOT = os.path.dirname(os.path.abspath(__file__))

SCENARIO_FOLDER = os.path.join(ROOT, "data", "scenarios")

SCENARIOS = [
    "example",
    "no_solar_battery",
    "high_solar",
    "restricted_supply"
]

SEED = 42


# Load a household scenario and create its scheduling problem
def load_scenario(name):
    folder = os.path.join(SCENARIO_FOLDER, name)

    kb = load_knowledge_base(folder)
    problem = make_problem(kb)

    return problem


# Display basic information about the scheduling problem
def show_scenario(name, problem):
    print("\n" + "=" * 50)
    print("Scenario:", name)
    print("=" * 50)

    print("Supply limit:", problem["supply_limit"], "kW")
    print("Flexible appliances:", len(problem["names"]))
    print("Maximum solar generation:", max(problem["solar"]), "kW")

    print("\nAppliance domain sizes:")

    for i in range(len(problem["names"])):
        print(
            problem["names"][i],
            "-",
            len(problem["domains"][i]),
            "possible start times"
        )


def main():
    for name in SCENARIOS:
        problem = load_scenario(name)

        show_scenario(name, problem)


if __name__ == "__main__":
    main()