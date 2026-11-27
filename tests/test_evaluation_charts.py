"""
Tests for evaluation_charts.py. The charts are drawn from a small hand-made
results dict, so the slow exhaustive search on high_solar never runs here;
only the quick example scenario is searched for real.
Run from the repository root:
    pytest tests/test_evaluation_charts.py
"""

import json
import os
import sys

import matplotlib
matplotlib.use("Agg")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import src.evaluation_charts as ec                                  # noqa: E402
from src.evaluation import load_scenario                            # noqa: E402


def energy(cost, co2, grid, valid=True):
    return {"cost_eur": cost, "co2_kg": co2, "grid_kwh": grid, "valid": valid}


FAKE = {
    "example": {
        "energy": {ec.BASELINE: energy(12.6, 11.4, 38.4), ec.OPTIMISED: energy(9.1, 8.8, 38.4)},
        "optimality": {"valid_schedules": 6240, "nodes": 6580, "time_ms": 137.0,
                       "optimal_score": 9.8,
                       "gaps": {"Hill climbing": 0.0, "Random restart": 0.0,
                                "Simulated annealing": 0.002}},
    },
    "restricted_supply": {
        "energy": {ec.BASELINE: energy(12.6, 11.4, 38.4, valid=False),
                   ec.OPTIMISED: energy(9.1, 8.8, 38.4)},
        "optimality": {"valid_schedules": 2150, "nodes": 2480, "time_ms": 1500.0,
                       "optimal_score": 9.8,
                       "gaps": {"Hill climbing": None, "Random restart": 0.0,
                                "Simulated annealing": 0.9}},
    },
}


def test_make_all_writes_both_charts(tmp_path):
    paths = ec.make_all(FAKE, str(tmp_path))
    assert [os.path.basename(p) for p in paths] == ["savings_by_scenario.png",
                                                    "algorithm_scaling.png"]
    for p in paths:
        assert os.path.dirname(p) == str(tmp_path / "images")
        assert os.path.getsize(p) > 0


def test_change_text():
    assert ec.change_text(12.6, 9.1) == "(-28%)"
    assert ec.change_text(38.4, 38.4) == "(0%)"
    assert ec.change_text(43.9, 43.89) == "(0%)"      # never "-0%"
    assert ec.change_text(0, 5) == "(0%)"             # no division by zero


def test_energy_results_example():
    results = ec.energy_results(load_scenario("example"))
    base, best = results[ec.BASELINE], results[ec.OPTIMISED]
    assert best["valid"] and best["cost_eur"] < base["cost_eur"]


def test_optimality_results_example():
    results = ec.optimality_results(load_scenario("example"))
    assert results["valid_schedules"] == 6240
    assert set(results["gaps"]) == set(ec.ALGORITHMS)
    assert all(g is None or g >= 0 for g in results["gaps"].values())
    assert results["gaps"]["Random restart"] == 0.0


def test_saved_results_are_reused(tmp_path, monkeypatch):
    path = tmp_path / "results.json"
    path.write_text(json.dumps(FAKE))

    def must_not_run(scenarios):
        raise AssertionError("collect() ran although results were saved")

    monkeypatch.setattr(ec, "collect", must_not_run)
    assert ec.load_or_collect(str(path), scenarios=list(FAKE)) == FAKE


def test_refresh_or_other_scenarios_rerun(tmp_path, monkeypatch):
    path = tmp_path / "results.json"
    path.write_text(json.dumps(FAKE))
    calls = []
    monkeypatch.setattr(ec, "collect", lambda scenarios: calls.append(scenarios) or {"x": 1})

    ec.load_or_collect(str(path), refresh=True, scenarios=list(FAKE))
    ec.load_or_collect(str(path), scenarios=["example"])      # saved file has 2 scenarios
    assert len(calls) == 2
    assert json.loads(path.read_text()) == {"x": 1}           # new results were saved
