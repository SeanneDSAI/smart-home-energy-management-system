"""
Interactive command-line interface

Pick an option from the menu by typing its number.
"""
import os
import random
import sys

from src.knowledge_base import load_knowledge_base, describe_kb, slot_to_time
from src.controller import print_day
from src.csp import make_problem, is_valid
from src.localsearch import (cost, random_state, random_restarting_hillclimbing,
                             simulated_annealing)

ROOT = os.path.dirname(os.path.abspath(__file__))
IMAGES = os.path.join(ROOT, "images")

# The searches are random. A fixed seed makes every run give the same results,
# so the numbers in the report and the demo always match.
SEED = 1

MENU = """
=======================================
 Scenario: {scenario}
---------------------------------------
 1  Show the scenario
 2  Find the best schedule
 3  Run the battery controller
 4  Make charts (saved to images/)
 q  Quit
======================================="""


def ask(prompt, default=""):
    """input() that returns the default on a blank answer (or Ctrl+D)."""
    try:
        answer = input(prompt).strip()
    except EOFError:
        return default
    return answer or default


# ---------------------------------------------------------------------------
# Menu actions. Each takes the session dict and may update it.
# ---------------------------------------------------------------------------

def show_scenario(session):
    print()
    print(describe_kb(session["kb"]))


def find_best_schedule(session):
    """Run both searches, compare them with the baseline, then show the winner."""
    problem = session["problem"]
    if not problem["names"]:
        print("\nNo flexible appliances in this scenario, nothing to schedule.")
        return

    print("\nRunning hill climbing and simulated annealing...")
    schedules = {
        "Run as early as possible": [domain[0] for domain in problem["domains"]],
        "Hill climbing": random_restarting_hillclimbing(problem),
        "Simulated annealing": simulated_annealing(problem, random_state(problem)),
    }
    session["schedules"] = schedules

    print("\n  %-26s %8s  %s" % ("Schedule", "Cost", "Valid"))
    for name, schedule in schedules.items():
        print("  %-26s %8.3f  %s" % (name, cost(problem, schedule),
                                     "yes" if is_valid(problem, schedule) else "NO"))

    winner = min(list(schedules)[1:], key=lambda name: cost(problem, schedules[name]))
    best = schedules[winner]
    print("\nBest schedule (%s):" % winner)
    print("\n  %-18s %6s  %s" % ("Appliance", "kW", "Runs"))
    for i, name in enumerate(problem["names"]):
        start = best[i]
        noisy = "  (noisy)" if problem["noisy"][i] else ""
        print("  %-18s %6.1f  %s-%s%s" % (name, problem["power"][i], slot_to_time(start),
                                         slot_to_time(start + problem["duration"][i]), noisy))


def run_controller(session):
    print("\nBattery controller (slots where it acts or gives advice):\n")
    print_day(session["kb"])
    print("\nNote: the controller does not yet include the scheduled flexible appliances.")


def make_charts(session):
    import matplotlib.pyplot as plt
    from src.visualisation import make_all


    if not session["schedules"]:
        print("\nRunning the searches first...")
    paths = make_all(session["kb"], IMAGES, schedules=session["schedules"])

    images = [p for p in paths if p.endswith(".png")]
    print("\nSaved to %s:" % IMAGES)
    for number, path in enumerate(images, 1):
        print("  %d  %s" % (number, os.path.basename(path)))
    print("  (plus day_slots.csv with the numbers behind them)")

    while True:
        choice = ask("\nShow a chart? Number, 'a' for all, Enter to skip: ").lower()
        if not choice:
            return
        if choice == "a":
            picked = images
        elif choice.isdigit() and 1 <= int(choice) <= len(images):
            picked = [images[int(choice) - 1]]
        else:
            print("Pick a number from 1 to %d." % len(images))
            continue
        # One window per chart; plt.show() waits until they are all closed
        for path in picked:
            plt.figure(figsize=(11, 5))
            plt.imshow(plt.imread(path))
            plt.axis("off")
        print("Close the chart window(s) to carry on.")
        plt.show()


ACTIONS = {"1": show_scenario, "2": find_best_schedule, "3": run_controller, "4": make_charts}


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data", "scenarios", "example")
    try:
        kb = load_knowledge_base(folder)
        problem = make_problem(kb)
    except (OSError, ValueError, KeyError) as error:
        print("Could not load scenario '%s': %s" % (folder, error))
        return 1
    session = {"kb": kb, "problem": problem, "schedules": None,
               "name": os.path.relpath(os.path.abspath(folder), ROOT)}

    while True:
        print(MENU.format(scenario=session["name"]))
        choice = ask("Choose an option: ").lower()
        if choice in ("q", "quit", "exit"):
            print("Bye!")
            return 0
        action = ACTIONS.get(choice)
        if action is None:
            print("Unknown option '%s'." % choice)
            continue
        random.seed(SEED)    
        try:
            action(session)
        except KeyboardInterrupt:
            print("\nCancelled.")
        ask("\nPress Enter to go back to the menu...")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nBye!")
