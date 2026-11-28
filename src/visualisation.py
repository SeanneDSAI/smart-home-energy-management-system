"""
Visualisation: charts of one simulated day.
For a scenario they are saved in outputs/<scenario>/:

  images/energy_use.png         household demand by source (stacked) against solar
                                and the supply limit, using the optimised schedule
  images/electricity_price.png  tariff price over the day
  images/carbon_intensity.png   grid carbon intensity over the day
  images/battery.png            battery state of charge and the controller's actions
                                (only when the scenario has a battery)
  images/schedule_cost.png      daily cost of the baseline vs the optimised schedules
  images/dashboard.png          all of the above on one page

Each chart is drawn by one draw_* function that paints onto an axis, so the same
code makes both the single-chart PNG and its panel in the dashboard.

"""

import os
import sys

import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUTPUTS = os.path.join(ROOT, "outputs")

from src.knowledge_base import load_knowledge_base, SLOTS_PER_DAY
from src.controller import run_day
from src.csp import make_problem
from src.scheduler import solve_all, schedule_costs, best_schedule

SLOT_HOURS = 0.5

# Colours for the series, always used in this order
COLOURS = ["#257de0", "#f47230", "#00b894", "#f2a600",
           "#ee7fac", "#008a17", "#6a4ce2", "#ec4647"]

ACTION_LABELS = {"charge_grid": "Charge from grid",
                 "charge_solar": "Charge from solar",
                 "discharge": "Discharge to home"}

# x axis for every time chart: the hour each slot starts at (0, 0.5, 1, ... 23.5)
HOURS = [s * SLOT_HOURS for s in range(SLOTS_PER_DAY)]
HOUR_TICKS = list(range(0, 25, 3))
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


def day_data(kb, schedule, problem=None):
    """One dict per slot with demand, solar, grid import, price, carbon and battery.
    Demand split by appliance is in the returned sources. Pass problem if it has
    already been built from kb, to avoid building it again."""
    problem = problem or make_problem(kb)
    sources = demand_by_source(problem, schedule)
    battery_log = run_day(kb, schedule)
    rows = []
    for s in range(SLOTS_PER_DAY):
        demand = sum(load[s] for load in sources.values())
        solar = problem["solar"][s]
        rows.append({"total_demand_kw": round(demand, 3),
                     "solar_kw": solar,
                     "grid_import_kw": round(max(0.0, demand - solar), 3),
                     "price_eur_per_kwh": problem["price"][s],
                     "carbon_g_per_kwh": problem["carbon"][s],
                     "battery_soc_kwh": battery_log[s]["soc_kwh"],
                     "battery_action": battery_log[s]["battery_action"] or ""})
    return problem, sources, rows

# ---------------------------------------------------------------------------
# Charts: each draw_* function paints onto an axis it is given
# ---------------------------------------------------------------------------

def time_axis(ax, title, ylabel):
    """Shared look for every chart that runs across the day."""
    ax.set_title(title, loc="left", fontweight="bold")
    ax.set_xlabel("Time of day")
    ax.set_ylabel(ylabel)
    ax.set_xlim(0, 24)
    ax.set_xticks(HOUR_TICKS)
    ax.set_xticklabels(HOUR_LABELS)
    ax.grid(axis="y", alpha=0.3)


def draw_energy(ax, problem, sources, rows):
    """Demand by source as stacked bars, with solar and the supply limit."""
    bottom = [0.0] * SLOTS_PER_DAY
    for colour, (name, load) in zip(COLOURS, sources.items()):
        ax.bar(HOURS, load, width=SLOT_HOURS, bottom=bottom, align="edge",
               color=colour, edgecolor="white", label=name)
        bottom = [b + v for b, v in zip(bottom, load)]
    ax.step(HOURS + [24], [r["solar_kw"] for r in rows] + [0], where="post",
            color="black", linewidth=2, label="Solar generation")
    ax.axhline(problem["supply_limit"], color="grey", linestyle="--",
               label="Supply limit (%.0f kW)" % problem["supply_limit"])
    time_axis(ax, "Energy use over the day", "Power (kW)")
    ax.legend(loc="upper left", fontsize=8)


def draw_step(ax, rows, column, title, ylabel):
    """A value that holds steady for each half hour (price, carbon)."""
    values = [r[column] for r in rows]
    ax.step(HOURS + [24], values + [values[-1]], where="post", color=COLOURS[0], linewidth=2)
    time_axis(ax, title, ylabel)
    ax.set_ylim(0, max(values) * 1.2)


def draw_price(ax, rows):
    draw_step(ax, rows, "price_eur_per_kwh", "Electricity price", "EUR per kWh")


def draw_carbon(ax, rows):
    draw_step(ax, rows, "carbon_g_per_kwh", "Grid carbon intensity", "g CO2 per kWh")


def draw_battery(ax, kb, rows):
    """Battery state of charge, with a marker for each action the controller takes."""
    time_axis(ax, "Battery state of charge", "Stored energy (kWh)")
    battery = kb["graph"].get("battery")
    if not battery:
        ax.text(12, 0.5, "No battery in this scenario", ha="center")
        return
    ends = [h + SLOT_HOURS for h in HOURS]      # the charge is recorded at the end of each slot
    soc = [r["battery_soc_kwh"] for r in rows]

    ax.plot(ends, soc, color=COLOURS[0], linewidth=2, label="Charge level")
    for colour, (action, label) in zip(COLOURS[1:], ACTION_LABELS.items()):
        picked = [s for s in range(SLOTS_PER_DAY) if rows[s]["battery_action"] == action]
        ax.scatter([ends[s] for s in picked], [soc[s] for s in picked],
                   color=colour, zorder=3, label=label)
    ax.axhline(battery["capacity_kwh"], color="grey", linestyle="--", label="Capacity")
    ax.axhline(battery["min_charge_kwh"], color="grey", linestyle=":", label="Reserve")
    ax.set_ylim(0, battery["capacity_kwh"] * 1.15)
    ax.legend(loc="lower left", fontsize=8)


def draw_cost(ax, costs):
    """Horizontal bar per schedule, with its cost written next to the bar.
    costs: {schedule name: cost score}, as from schedule_costs."""
    ax.set_title("Daily cost by schedule", loc="left", fontweight="bold")
    if not costs:
        ax.text(0.5, 0.5, "No flexible appliances to schedule", ha="center")
        return
    ax.barh(list(costs), list(costs.values()), color=COLOURS[0])
    for i, c in enumerate(costs.values()):
        ax.text(c, i, "  %.3f" % c, va="center")
    ax.invert_yaxis()                           # first schedule on top
    ax.set_xlabel("Cost score (EUR + carbon + constraint penalties)")
    ax.set_xlim(0, max(costs.values()) * 1.2)
    ax.grid(axis="x", alpha=0.3)


def save_single(path, size, draw, *args):
    """One chart on its own figure, saved as a PNG."""
    fig, ax = plt.subplots(figsize=size)
    draw(ax, *args)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_dashboard(kb, problem, sources, rows, costs, path):
    """One page: energy use across the top, then price and carbon, then the
    battery and the schedule costs, under a headline with the key numbers.
    costs: {schedule name: cost score}, the baseline first."""
    fig = plt.figure(figsize=(16, 13))
    grid = fig.add_gridspec(3, 2, height_ratios=[1.4, 1, 1])
    draw_energy(fig.add_subplot(grid[0, :]), problem, sources, rows)
    draw_price(fig.add_subplot(grid[1, 0]), rows)
    draw_carbon(fig.add_subplot(grid[1, 1]), rows)
    draw_battery(fig.add_subplot(grid[2, 0]), kb, rows)
    draw_cost(fig.add_subplot(grid[2, 1]), costs)

    used = sum(r["total_demand_kw"] for r in rows) * SLOT_HOURS
    from_grid = sum(r["grid_import_kw"] for r in rows) * SLOT_HOURS
    headline = "%.1f kWh used  |  %.1f kWh from the grid after solar" % (used, from_grid)
    if costs:
        values = list(costs.values())
        saving = values[0] - min(values[1:] or values)
        headline += "  |  best schedule saves %.2f (%.0f%%) on the baseline" % (
            saving, 100 * saving / values[0])
    fig.suptitle("SHEMS dashboard\n" + headline, fontsize=14, fontweight="bold")

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def make_all(kb, out_dir, schedules):
    """Write every chart and the dashboard to out_dir/images; return the paths written.
    schedules: {name: schedule} as from scheduler.solve_all, baseline first.
    Empty when the scenario has no flexible appliances to schedule."""
    images = os.path.join(out_dir, "images")
    os.makedirs(images, exist_ok=True)
    problem = make_problem(kb)
    costs, best = {}, []
    if schedules:
        costs = schedule_costs(problem, schedules)
        best = schedules[best_schedule(costs)]
    problem, sources, rows = day_data(kb, best, problem)

    paths = []

    def out(name):
        paths.append(os.path.join(images, name))
        return paths[-1]

    save_single(out("energy_use.png"), (11, 5), draw_energy, problem, sources, rows)
    save_single(out("electricity_price.png"), (11, 3), draw_price, rows)
    save_single(out("carbon_intensity.png"), (11, 3), draw_carbon, rows)
    if "battery" in kb["graph"]:
        save_single(out("battery.png"), (11, 4), draw_battery, kb, rows)
    if costs:
        save_single(out("schedule_cost.png"), (8, 3), draw_cost, costs)
    plot_dashboard(kb, problem, sources, rows, costs, out("dashboard.png"))
    return paths


if __name__ == "__main__":
    # python -m src.visualisation [scenario folder] [output folder]
    # default output folder: outputs/<scenario name>
    args = sys.argv[1:]
    folder = args[0] if args else os.path.join(ROOT, "data", "scenarios", "example")
    out_dir = args[1] if len(args) > 1 else os.path.join(OUTPUTS, os.path.basename(os.path.normpath(folder)))
    kb = load_knowledge_base(folder)
    problem = make_problem(kb)
    schedules = solve_all(problem) if problem["names"] else {}
    for p in make_all(kb, out_dir, schedules):
        print("wrote", p)