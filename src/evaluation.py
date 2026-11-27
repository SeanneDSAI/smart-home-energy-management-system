"""
Evaluation of the Smart Home Energy Management System.

Compares CSP and local search algorithms across different
household scenarios.

Run from the repository root:
    python -m src.evaluation
"""

import os
import sys
import time
import random

# The repository root (one level up from src/), put on the path so
# "from src.x import ..." also works when this file is run directly
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

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


# Compare backtracking with different combinations of heuristics
def evaluate_csp(problem):

    print("\nCSP Performance Comparison")
    print("-" * 75)

    configurations = [
        ("Backtracking", False, False),
        ("Backtracking + MRV", True, False),
        ("Backtracking + FC", False, True),
        ("Backtracking + MRV + FC", True, True)
    ]

    print(f"{'Algorithm':<28} {'Solutions':>10} {'Nodes':>10} {'Time (ms)':>12} {'Valid':>8}")

    for name, mrv, fc in configurations:

        start = time.perf_counter()

        schedules, nodes = backtracking_search(
            problem,
            limit=100,
            use_mrv=mrv,
            use_forward_checking=fc
        )

        elapsed = (time.perf_counter() - start) * 1000

        valid = len(schedules) > 0

        for schedule in schedules:
            if len(schedule) != len(problem["names"]):
                valid = False

            elif not is_valid(problem, schedule):
                valid = False

        print(f"{name:<28} {len(schedules):>10} {nodes:>10} {elapsed:>12.3f} {str(valid):>8}")


# Check that a schedule is complete and satisfies the constraints
def check_schedule(problem, schedule):
    if schedule is None:
        return False

    if len(schedule) != len(problem["names"]):
        return False

    return is_valid(problem, schedule)


# Compare local search algorithms over multiple runs
def evaluate_local_search(problem, runs=10):

    print("\nLocal Search Performance Comparison")
    print("-" * 85)

    algorithms = [
        "Earliest start",
        "Random schedule",
        "Hill climbing",
        "Random restart",
        "Simulated annealing"
    ]

    print(f"{'Algorithm':<24} {'Avg Cost':>10} {'Best Cost':>10} {'Time (ms)':>12} {'Valid %':>10}")

    for name in algorithms:

        scores = []
        times = []
        valid_count = 0

        for run in range(runs):

            random.seed(SEED + run)
            initial = random_state(problem)

            start = time.perf_counter()

            if name == "Earliest start":
                schedule = [domain[0] for domain in problem["domains"]]

            elif name == "Random schedule":
                schedule = list(initial)

            elif name == "Hill climbing":
                schedule = hill_climbing(problem, initial)

            elif name == "Random restart":
                random.seed(SEED + run)
                schedule = random_restarting_hillclimbing(
                    problem, restarts=20
                )

            elif name == "Simulated annealing":
                schedule = simulated_annealing(problem, initial)

            elapsed = (time.perf_counter() - start) * 1000

            scores.append(cost(problem, schedule))
            times.append(elapsed)

            if check_schedule(problem, schedule):
                valid_count += 1

        average_cost = sum(scores) / runs
        best_cost = min(scores)
        average_time = sum(times) / runs
        valid_percentage = (valid_count / runs) * 100

        print(f"{name:<24} {average_cost:>10.3f} {best_cost:>10.3f} {average_time:>12.3f} {valid_percentage:>9.1f}%")



# Calculate electricity costs, carbon emissions and grid energy usage
def energy_metrics(problem, schedule):

    assignment = dict(enumerate(schedule))
    demand = load_per_slot(problem, assignment)

    electricity_cost = 0.0
    carbon_emissions = 0.0
    grid_energy = 0.0

    for s in range(48):

        grid = max(0.0, demand[s] - problem["solar"][s])

        kwh = grid * 0.5

        grid_energy += kwh
        electricity_cost += kwh * problem["price"][s]
        carbon_emissions += kwh * problem["carbon"][s]

    return electricity_cost, carbon_emissions / 1000, grid_energy


# Compare electricity costs and carbon emissions before and after optimisation
def evaluate_energy(problem):

    print("\nEnergy Performance Comparison")
    print("-" * 85)

    random.seed(SEED)

    baseline = [domain[0] for domain in problem["domains"]]

    hill = random_restarting_hillclimbing(
        problem, restarts=20
    )

    random.seed(SEED)

    annealing = simulated_annealing(
        problem, random_state(problem)
    )

    schedules = [
        ("Earliest start", baseline),
        ("Random restart", hill),
        ("Simulated annealing", annealing)
    ]

    print(f"{'Algorithm':<24} {'Cost (EUR)':>12} {'CO2 (kg)':>12} {'Grid (kWh)':>12} {'Valid':>8}")

    for name, schedule in schedules:

        money, carbon, energy = energy_metrics(problem, schedule)

        valid = check_schedule(problem, schedule)

        print(f"{name:<24} {money:>12.3f} {carbon:>12.3f} {energy:>12.3f} {str(valid):>8}")


# Compare local search results against the optimal feasible schedule
def evaluate_optimal_solution(problem):

    print("\nOptimal Solution Comparison")
    print("-" * 75)

    start = time.perf_counter()

    schedules, nodes = backtracking_search(
        problem,
        limit=None,
        use_mrv=True,
        use_forward_checking=True
    )

    if not schedules:
        print("No feasible schedules found.")
        return

    # Find the valid schedule with the lowest objective score
    optimal = min(schedules, key=lambda s: cost(problem, s))
    optimal_cost = cost(problem, optimal)

    elapsed = (time.perf_counter() - start) * 1000

    print("Total valid schedules:", len(schedules))
    print("Search nodes visited:", nodes)
    print("Exhaustive search time:", round(elapsed, 3), "ms")
    print("Optimal objective score:", round(optimal_cost, 3))

    random.seed(SEED)
    initial = random_state(problem)

    hill = hill_climbing(problem, initial)

    random.seed(SEED)
    restart = random_restarting_hillclimbing(
        problem, restarts=20
    )

    random.seed(SEED)
    annealing = simulated_annealing(
        problem, random_state(problem)
    )

    results = [
        ("Hill climbing", hill),
        ("Random restart", restart),
        ("Simulated annealing", annealing)
    ]

    print(f"\n{'Algorithm':<24} {'Score':>10} {'Gap':>10} {'Optimal':>10}")

    for name, schedule in results:

        score = cost(problem, schedule)

        if not check_schedule(problem, schedule):
            print(f"{name:<24} {score:>10.3f} {'N/A':>10} {'Invalid':>10}")
            continue

        gap = max(0.0, score - optimal_cost)

        reached_optimal = abs(score - optimal_cost) < 1e-9

        print(f"{name:<24} {score:>10.3f} {gap:>10.6f} {str(reached_optimal):>10}")



def main():
    for name in SCENARIOS:
        problem = load_scenario(name)

        show_scenario(name, problem)

        evaluate_csp(problem)

        evaluate_local_search(problem)

        evaluate_energy(problem)

        evaluate_optimal_solution(problem)


if __name__ == "__main__":
    main()