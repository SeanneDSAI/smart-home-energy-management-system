"""
Charts that compare the scenarios, built from the same runs as evaluation.py.

They are saved in outputs/evaluation/:

  images/savings_by_scenario.png   baseline vs optimised schedule in every scenario:
                                   electricity cost, carbon and energy bought from the grid
  images/algorithm_scaling.png     how far each local search ends from the true optimum,
                                   and how big the exhaustive search for that optimum gets
  data/results.json                the numbers both charts are drawn from

The exhaustive search on high_solar takes 30-90 seconds, so the numbers are saved
to data/results.json and reused. Pass --refresh to rerun them.

Run from the repository root:
    python -m src.evaluation_charts [output folder] [--refresh]   (default: outputs/evaluation)
"""

import argparse
import json
import os
import random
import sys
import time

import matplotlib.pyplot as plt

# the repository root, so "from src.x import ..." works when run directly too
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.evaluation import (SCENARIOS, SEED, ROOT, load_scenario, energy_metrics,
                        check_schedule)
from src.csp import backtracking_search
from src.localsearch import (random_state, cost, hill_climbing,
                             random_restarting_hillclimbing, simulated_annealing)
from src.visualisation import COLOURS

OUT_DIR = os.path.join(ROOT, "outputs", "evaluation")


def results_path(out_dir):
    """Where the numbers for the charts in out_dir are saved."""
    return os.path.join(out_dir, "data", "results.json")

SCENARIO_LABELS = {"example": "Example",
                   "no_solar_battery": "No solar\nor battery",
                   "high_solar": "High solar",
                   "restricted_supply": "Restricted\nsupply"}

BASELINE = "Earliest start"
OPTIMISED = "Random restart"
ALGORITHMS = ["Hill climbing", "Random restart", "Simulated annealing"]
BASELINE_COLOUR = "#9aa0a6"          # neutral grey: the baseline is the reference
TEXT = "#333333"
MUTED = "#666666"


# ---------------------------------------------------------------------------
# Data: run the searches once per scenario, seeded as in evaluation.py
# ---------------------------------------------------------------------------

def energy_results(problem):
    """{schedule name: {cost_eur, co2_kg, grid_kwh, valid}} for the baseline and
    the optimised schedule, seeded as in evaluation.evaluate_energy."""
    random.seed(SEED)
    schedules = {BASELINE: [d[0] for d in problem["domains"]],
                 OPTIMISED: random_restarting_hillclimbing(problem, restarts=20)}
    results = {}
    for name, schedule in schedules.items():
        money, carbon, grid = energy_metrics(problem, schedule)
        results[name] = {"cost_eur": money, "co2_kg": carbon, "grid_kwh": grid,
                         "valid": check_schedule(problem, schedule)}
    return results


def optimality_results(problem):
    """Size and time of the exhaustive search, the optimal score, and each local
    search's gap to it, seeded as in evaluation.evaluate_optimal_solution.
    A gap is None when that algorithm's schedule breaks a constraint."""
    start = time.perf_counter()
    every, nodes = backtracking_search(problem, limit=None, use_mrv=True,
                                       use_forward_checking=True)
    optimal = min(cost(problem, s) for s in every) if every else None
    elapsed = (time.perf_counter() - start) * 1000

    random.seed(SEED)
    hill = hill_climbing(problem, random_state(problem))
    random.seed(SEED)
    restart = random_restarting_hillclimbing(problem, restarts=20)
    random.seed(SEED)
    annealing = simulated_annealing(problem, random_state(problem))

    gaps = {}
    for name, schedule in zip(ALGORITHMS, (hill, restart, annealing)):
        if optimal is None or not check_schedule(problem, schedule):
            gaps[name] = None
        else:
            gaps[name] = max(0.0, cost(problem, schedule) - optimal)

    return {"valid_schedules": len(every), "nodes": nodes, "time_ms": elapsed,
            "optimal_score": optimal, "gaps": gaps}


def collect(scenarios=SCENARIOS):
    """{scenario: {"energy": ..., "optimality": ...}} for every scenario."""
    results = {}
    for name in scenarios:
        print("running", name, "...")
        problem = load_scenario(name)
        results[name] = {"energy": energy_results(problem),
                         "optimality": optimality_results(problem)}
    return results


def load_or_collect(path, refresh=False, scenarios=SCENARIOS):
    """Reuse the results saved at path if they cover these scenarios; otherwise
    run them and save them there."""
    if not refresh and os.path.exists(path):
        with open(path) as f:
            saved = json.load(f)
        if list(saved) == list(scenarios):
            return saved
    results = collect(scenarios)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(results, f, indent=2)
    return results


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def style(ax, title, ylabel):
    """Quiet axes: left-aligned bold title, light y grid, no top/right frame."""
    ax.set_title(title, loc="left", fontweight="bold", color=TEXT)
    ax.set_ylabel(ylabel, color=MUTED)
    ax.grid(axis="y", alpha=0.3)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(colors=MUTED)


def scenario_axis(ax, scenarios):
    ax.set_xticks(range(len(scenarios)))
    ax.set_xticklabels([SCENARIO_LABELS.get(s, s) for s in scenarios], color=TEXT)


def bar_label(ax, x, y, text, top):
    """Value written just above a bar."""
    ax.text(x, y + top * 0.02, text, ha="center", va="bottom", fontsize=8, color=TEXT)


SAVINGS_PANELS = [("cost_eur", "Electricity cost", "EUR per day", "%.2f"),
                  ("co2_kg", "Carbon emissions", "kg CO2 per day", "%.2f"),
                  ("grid_kwh", "Energy bought from the grid", "kWh per day", "%.1f")]


def change_text(before, after):
    """'(-28%)', or '(0%)' when it rounds to zero (never '-0%')."""
    change = round(100 * (after - before) / before) if before else 0
    return "(0%)" if change == 0 else "(%+d%%)" % change


def draw_savings(axes, results):
    """One panel per measure; in each, a baseline and an optimised bar per scenario.
    The optimised bar shows its change from the baseline, and a baseline that
    breaks a constraint is hatched."""
    scenarios = list(results)
    width = 0.38
    xs = range(len(scenarios))
    invalid = [not results[s]["energy"][BASELINE]["valid"] for s in scenarios]
    for ax, (key, title, unit, fmt) in zip(axes, SAVINGS_PANELS):
        base = [results[s]["energy"][BASELINE][key] for s in scenarios]
        best = [results[s]["energy"][OPTIMISED][key] for s in scenarios]
        top = max(base + best) or 1.0
        bars = ax.bar([x - width / 2 for x in xs], base, width, color=BASELINE_COLOUR,
                      edgecolor="white", linewidth=2, label="Run as early as possible")
        for bar, bad in zip(bars, invalid):
            if bad:
                bar.set_hatch("///")
        ax.bar([x + width / 2 for x in xs], best, width, color=COLOURS[0],
               edgecolor="white", linewidth=2,
               label="Optimised (random-restart hill climbing)")
        for x, b, o in zip(xs, base, best):
            bar_label(ax, x - width / 2, b, fmt % b, top)
            bar_label(ax, x + width / 2, o, (fmt % o) + "\n" + change_text(b, o), top)
        style(ax, title, unit)
        scenario_axis(ax, scenarios)
        ax.set_ylim(0, top * 1.3)
    if any(invalid):
        # legend-only bar, to explain the hatching
        axes[0].bar([0], [0], color=BASELINE_COLOUR, hatch="///", edgecolor="white",
                    label="Baseline breaks the supply limit")
    axes[0].legend(loc="upper left", fontsize=8, frameon=False)


def draw_gaps(ax, results):
    """Gap to the optimal score: one bar per local search per scenario."""
    scenarios = list(results)
    width = 0.8 / len(ALGORITHMS)
    gaps = {a: [results[s]["optimality"]["gaps"][a] for s in scenarios] for a in ALGORITHMS}
    top = max([g for gs in gaps.values() for g in gs if g is not None] + [0.0]) or 1.0
    for k, (colour, name) in enumerate(zip(COLOURS, ALGORITHMS)):
        xs = [x + (k - (len(ALGORITHMS) - 1) / 2) * width for x in range(len(scenarios))]
        # a gap of 0 still gets a thin sliver, so every algorithm's colour shows
        heights = [max(g or 0.0, top * 0.008) for g in gaps[name]]
        ax.bar(xs, heights, width, color=colour, edgecolor="white", linewidth=1, label=name)
        for x, g in zip(xs, gaps[name]):
            text = "invalid" if g is None else ("0" if g < 1e-9 else "%.3f" % g)
            bar_label(ax, x, g or 0.0, text, top)
    style(ax, "Distance from the optimal schedule", "Score above optimal (lower is better)")
    scenario_axis(ax, scenarios)
    ax.set_ylim(0, top * 1.2)
    ax.legend(loc="upper left", fontsize=8, frameon=False)


def draw_search_size(ax, results):
    """Valid schedules the exhaustive search checks (log scale), labelled with
    how long it took."""
    scenarios = list(results)
    counts = [results[s]["optimality"]["valid_schedules"] for s in scenarios]
    ax.bar(range(len(scenarios)), counts, 0.5, color=COLOURS[0],
           edgecolor="white", linewidth=2)
    ax.set_yscale("log")
    for x, s, n in zip(range(len(scenarios)), scenarios, counts):
        ms = results[s]["optimality"]["time_ms"]
        took = "%.1f s" % (ms / 1000) if ms >= 1000 else "%.0f ms" % ms
        ax.text(x, max(n, 1) * 1.15, "{:,}\n{}".format(n, took), ha="center",
                va="bottom", fontsize=8, color=TEXT)
    style(ax, "Size of the exhaustive search", "Valid schedules (log scale)")
    scenario_axis(ax, scenarios)
    ax.set_ylim(1, max(counts + [10]) * 20)


def plot_savings(results, path):
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2))
    draw_savings(axes, results)
    fig.suptitle("Baseline vs optimised schedule in each scenario",
                 fontsize=14, fontweight="bold", color=TEXT)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_scaling(results, path):
    fig, (gap_ax, size_ax) = plt.subplots(1, 2, figsize=(15, 5.2),
                                          gridspec_kw={"width_ratios": [1.5, 1]})
    draw_gaps(gap_ax, results)
    draw_search_size(size_ax, results)
    fig.suptitle("Local search quality and the cost of finding the optimum",
                 fontsize=14, fontweight="bold", color=TEXT)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def make_all(results, out_dir=OUT_DIR):
    """Write both charts to out_dir/images; return their paths."""
    images = os.path.join(out_dir, "images")
    os.makedirs(images, exist_ok=True)
    paths = [os.path.join(images, "savings_by_scenario.png"),
             os.path.join(images, "algorithm_scaling.png")]
    plot_savings(results, paths[0])
    plot_scaling(results, paths[1])
    return paths


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Charts comparing the SHEMS scenarios.")
    parser.add_argument("out_dir", nargs="?", default=OUT_DIR)
    parser.add_argument("--refresh", action="store_true",
                        help="rerun the searches instead of reusing data/results.json")
    args = parser.parse_args()
    results = load_or_collect(results_path(args.out_dir), args.refresh)
    for p in make_all(results, args.out_dir):
        print("wrote", p)
