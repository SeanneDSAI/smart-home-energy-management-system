"""
Tests for src/visualisation.py: the per-slot day data, demand split by source
(including runs that wrap past midnight) and that every chart file is written.
Uses matplotlib's non-interactive Agg backend so no windows open.
Run from the repository root:
    pytest tests/test_visualisation.py
"""

import csv
import os
import sys

import matplotlib
matplotlib.use("Agg")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.knowledge_base import load_knowledge_base                     
from src.csp import make_problem                                       
from src.visualisation import pretty_name, day_data, make_all, demand_by_source  

KB = load_knowledge_base(os.path.join(ROOT, "data", "scenarios", "example"))
PROBLEM = make_problem(KB)
BASELINE = [d[0] for d in PROBLEM["domains"]]


def test_pretty_name():
    assert pretty_name("ev_charger") == "EV charger"


def test_day_data_has_48_slots():
    _, _, rows = day_data(KB, BASELINE)
    assert len(rows) == 48


def test_demand_adds_up():
    # each appliance's series holds exactly its power x its run time
    sources = demand_by_source(PROBLEM, BASELINE)
    for i, name in enumerate(PROBLEM["names"]):
        total = sum(sources[pretty_name(name)])
        assert abs(total - PROBLEM["power"][i] * PROBLEM["duration"][i]) < 1e-9


def test_demand_wraps_past_midnight():
    schedule = list(BASELINE)
    ev = PROBLEM["names"].index("ev_charger")
    schedule[ev] = 46                       # 23:00, runs 6 slots: 46, 47, 0, 1, 2, 3
    load = demand_by_source(PROBLEM, schedule)[pretty_name("ev_charger")]
    assert load[46] == load[47] == load[0] == load[3] == 7.0
    assert load[4] == 0.0                   # first slot after the run


def test_make_all_writes_charts(tmp_path):
    make_all(KB, str(tmp_path), schedules={"baseline": BASELINE, "hill": BASELINE})
    for name in ("energy_use.png", "electricity_price.png", "carbon_intensity.png",
                 "battery.png", "schedule_cost.png", "dashboard.png"):
        assert (tmp_path / "images" / name).exists()


def test_make_all_writes_data(tmp_path):
    make_all(KB, str(tmp_path), schedules={"baseline": BASELINE, "hill": BASELINE})
    with open(tmp_path / "data" / "day.csv") as f:
        day = list(csv.DictReader(f))
    assert len(day) == 48
    assert day[0]["time"] == "00:00" and day[47]["time"] == "23:30"
    assert "EV charger" in day[0]                       # one column per appliance

    with open(tmp_path / "data" / "schedules.csv") as f:
        schedules = list(csv.DictReader(f))
    assert [row["schedule"] for row in schedules] == ["baseline", "hill"]
    assert "ev_charger" in schedules[0]                 # its run time, e.g. "19:00-22:00"