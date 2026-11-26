"""
Visualisation: charts of one simulated day, saved as PNG files in images/.

  energy_use.png         household demand by source (stacked) against solar and
                         the supply limit, using the optimised schedule
  electricity_price.png  tariff price over the day
  carbon_intensity.png   grid carbon intensity over the day
  battery.png            battery state of charge and the controller's actions
                         (only when the scenario has a battery)
  schedule_cost.png      daily cost of the baseline vs the optimised schedules
  day_slots.csv          the numbers behind the charts, one row per slot

Needs matplotlib (pip install matplotlib). Run from the repository root:

    python -m src.visualisation                                  # example scenario -> images/
    python -m src.visualisation data/scenarios/<name> <out folder>
"""

import csv
import os
import sys

import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.knowledge_base import load_knowledge_base, SLOTS_PER_DAY
from src.controller import run_day
from src.csp import make_problem
from src.localsearch import (random_state, cost, random_restarting_hillclimbing,
                             simulated_annealing)

SLOT_HOURS = 0.5

# Colours for the series, always used in this order
COLOURS = ["#257de0", "#f47230", "#00b894", "#f2a600",
           "#ee7fac", "#008a17", "#6a4ce2", "#ec4647"]

ACTION_LABELS = {"charge_grid": "Charge from grid",
                 "charge_solar": "Charge from solar",
                 "discharge": "Discharge to home"}

# x axis for every time chart: the hour each slot starts at (0, 0.5, 1, ... 23.5)
HOURS = [s * SLOT_HOURS for s in range(SLOTS_PER_DAY)]
HOUR_TICKS = range(0, 25, 3)
HOUR_LABELS = ["%02d:00" % h for h in HOUR_TICKS]


# ---------------------------------------------------------------------------
# Data: everything the charts need, slot by slot
# ---------------------------------------------------------------------------

def demand_by_source(problem, schedule):
    """{series name: [kW per slot]}. Base load and fixed appliances are combined;
    each flexible appliance gets its own series, placed where the schedule runs it."""
    series = {"Base load + fixed": list(problem["background"])}
    for i, name in enumerate(problem["names"]):
        load = [0.0] * SLOTS_PER_DAY
        for step in range(problem["duration"][i]):
            load[(schedule[i] + step) % SLOTS_PER_DAY] += problem["power"][i]
        series[pretty_name(name)] = load
    return series


def pretty_name(name):
    """'ev_charger' -> 'EV charger', 'washing_machine' -> 'Washing machine'."""
    words = [w.upper() if len(w) <= 2 else w for w in name.split("_")]
    text = " ".join(words)
    return text[0].upper() + text[1:]


def solve_all(problem, restarts=20):
    """Baseline (earliest start) plus both search algorithms' schedules."""
    return {
        "Run as early as possible": [d[0] for d in problem["domains"]],
        "Hill climbing": random_restarting_hillclimbing(problem, restarts=restarts),
        "Simulated annealing": simulated_annealing(problem, random_state(problem)),
    }


def day_data(kb, schedule):
    """One dict per slot with demand, solar, grid import, price, carbon and battery."""
    problem = make_problem(kb)
    sources = demand_by_source(problem, schedule)
    battery_log = run_day(kb)
    rows = []
    for s in range(SLOTS_PER_DAY):
        demand = sum(load[s] for load in sources.values())
        solar = problem["solar"][s]
        row = {"slot": s, "time": "%02d:%02d" % (s // 2, (s % 2) * 30)}
        row.update({name: round(load[s], 3) for name, load in sources.items()})
        row.update({"total_demand_kw": round(demand, 3),
                    "solar_kw": solar,
                    "grid_import_kw": round(max(0.0, demand - solar), 3),
                    "price_eur_per_kwh": problem["price"][s],
                    "carbon_g_per_kwh": problem["carbon"][s],
                    "battery_soc_kwh": battery_log[s]["soc_kwh"],
                    "battery_action": battery_log[s]["battery_action"] or ""})
        rows.append(row)
    return problem, sources, rows


def write_csv(rows, path):
    with open(path, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def plot_energy_use(problem, sources, rows, path):
    """Demand by source as stacked bars, with solar and the supply limit."""
    plt.figure(figsize=(11, 5))

    bottom = [0.0] * SLOTS_PER_DAY
    for colour, (name, load) in zip(COLOURS, sources.items()):
        plt.bar(HOURS, load, width=SLOT_HOURS, bottom=bottom, align="edge",
                color=colour, edgecolor="white", label=name)
        bottom = [b + v for b, v in zip(bottom, load)]

    solar = [r["solar_kw"] for r in rows]
    plt.step(HOURS, solar, where="post", color="black", linewidth=2, label="Solar generation")
    plt.axhline(problem["supply_limit"], color="grey", linestyle="--",
                label="Supply limit (%.0f kW)" % problem["supply_limit"])

    plt.title("Energy use over the day")
    plt.xlabel("Time of day")
    plt.ylabel("Power (kW)")
    plt.xticks(HOUR_TICKS, HOUR_LABELS)
    plt.xlim(0, 24)
    plt.grid(axis="y", alpha=0.3)
    plt.legend(loc="upper left", fontsize=8)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def plot_price(rows, path):
    """Electricity price over the day."""
    price = [r["price_eur_per_kwh"] for r in rows]
    plt.figure(figsize=(11, 3))
    plt.step(HOURS + [24], price + [price[-1]], where="post", color=COLOURS[0], linewidth=2)
    plt.title("Electricity price")
    plt.xlabel("Time of day")
    plt.ylabel("EUR per kWh")
    plt.xticks(HOUR_TICKS, HOUR_LABELS)
    plt.xlim(0, 24)
    plt.ylim(0, max(price) * 1.2)
    plt.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def plot_carbon(rows, path):
    """Grid carbon intensity over the day."""
    carbon = [r["carbon_g_per_kwh"] for r in rows]
    plt.figure(figsize=(11, 3))
    plt.step(HOURS + [24], carbon + [carbon[-1]], where="post", color=COLOURS[0], linewidth=2)
    plt.title("Grid carbon intensity")
    plt.xlabel("Time of day")
    plt.ylabel("g CO2 per kWh")
    plt.xticks(HOUR_TICKS, HOUR_LABELS)
    plt.xlim(0, 24)
    plt.ylim(0, max(carbon) * 1.2)
    plt.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def plot_battery(kb, rows, path):
    """Battery state of charge, with a marker for each action the controller takes."""
    battery = kb["graph"]["battery"]
    ends = [h + SLOT_HOURS for h in HOURS]      # the charge is recorded at the end of each slot
    soc = [r["battery_soc_kwh"] for r in rows]

    plt.figure(figsize=(11, 4))
    plt.plot(ends, soc, color=COLOURS[0], linewidth=2, label="Charge level")
    for colour, (action, label) in zip(COLOURS[1:], ACTION_LABELS.items()):
        xs = [ends[s] for s in range(SLOTS_PER_DAY) if rows[s]["battery_action"] == action]
        ys = [soc[s] for s in range(SLOTS_PER_DAY) if rows[s]["battery_action"] == action]
        plt.scatter(xs, ys, color=colour, zorder=3, label=label)
    plt.axhline(battery["capacity_kwh"], color="grey", linestyle="--", label="Capacity")
    plt.axhline(battery["min_charge_kwh"], color="grey", linestyle=":", label="Reserve")

    plt.title("Battery state of charge")
    plt.xlabel("Time of day")
    plt.ylabel("Stored energy (kWh)")
    plt.xticks(HOUR_TICKS, HOUR_LABELS)
    plt.xlim(0, 24)
    plt.ylim(0, battery["capacity_kwh"] * 1.15)
    plt.grid(axis="y", alpha=0.3)
    plt.legend(loc="lower left", fontsize=8)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def plot_schedule_cost(problem, schedules, path):
    """Horizontal bar per schedule, with its cost written next to the bar."""
    names = list(schedules)
    costs = [cost(problem, schedules[n]) for n in names]

    plt.figure(figsize=(8, 3))
    plt.barh(names, costs, color=COLOURS[0])
    for i, c in enumerate(costs):
        plt.text(c, i, "  %.3f" % c, va="center")
    plt.gca().invert_yaxis()                    # first schedule on top
    plt.title("Daily cost by schedule")
    plt.xlabel("Cost score (EUR + carbon + constraint penalties)")
    plt.xlim(0, max(costs) * 1.15)
    plt.grid(axis="x", alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def make_all(kb, out_dir, restarts=20, schedules=None):
    """Build every chart and the CSV in out_dir; return the paths written.
    schedules: {name: schedule} as from solve_all, to chart results already found
    (the first entry is the baseline). Left out, the searches are run here."""
    os.makedirs(out_dir, exist_ok=True)
    problem = make_problem(kb)
    if problem["names"]:
        schedules = schedules or solve_all(problem, restarts)
        best = min(list(schedules.values())[1:], key=lambda s: cost(problem, s))
    else:
        schedules, best = {}, []
    problem, sources, rows = day_data(kb, best)

    paths = []

    def out(name):
        paths.append(os.path.join(out_dir, name))
        return paths[-1]

    plot_energy_use(problem, sources, rows, out("energy_use.png"))
    plot_price(rows, out("electricity_price.png"))
    plot_carbon(rows, out("carbon_intensity.png"))
    if "battery" in kb["graph"]:
        plot_battery(kb, rows, out("battery.png"))
    if schedules:
        plot_schedule_cost(problem, schedules, out("schedule_cost.png"))
    write_csv(rows, out("day_slots.csv"))
    return paths


if __name__ == "__main__":
    # python -m src.visualisation [scenario folder] [output folder]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    folder = sys.argv[1] if len(sys.argv) > 1 else os.path.join(root, "data", "scenarios", "example")
    out_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(root, "images")
    for p in make_all(load_knowledge_base(folder), out_dir):
        print("wrote", p)
