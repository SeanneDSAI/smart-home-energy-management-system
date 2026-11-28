"""
Tests for the controller working on top of the optimised schedule, and for the
supply-limit guard on grid charging.
Run from the repository root:
    python tests/test_controller_schedule.py   (or:  pytest tests/test_controller_schedule.py)
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.rules import RULES, forward_chain                          # noqa: E402
from src.knowledge_base import load_knowledge_base, hourly_value    # noqa: E402
from src.csp import make_problem, is_valid                          # noqa: E402
from src.controller import run_day, scheduled_load_kw, SLOT_HOURS   # noqa: E402


def load(name):
    return load_knowledge_base(os.path.join(ROOT, "data", "scenarios", name))


EXAMPLE = load("example")

# Best schedule for the example scenario, in make_problem order:
# washing machine 21:30, dishwasher 21:00, immersion heater 03:00, EV charger 02:00
BEST = [43, 42, 6, 4]

# A valid schedule for restricted_supply (8 kW) that runs the 7 kW EV charger
# from 00:00, the same time the battery wants to charge from the grid
EV_AT_MIDNIGHT = [43, 42, 10, 0]


def test_best_schedule_is_valid():
    assert is_valid(make_problem(EXAMPLE), BEST)
    assert is_valid(make_problem(load("restricted_supply")), EV_AT_MIDNIGHT)


def test_scheduled_load_places_each_appliance():
    load_kw = scheduled_load_kw(EXAMPLE, BEST)
    assert load_kw[4] == 7.0                    # EV charger alone at 02:00
    assert load_kw[6] == 10.0                   # EV charger + immersion heater at 03:00
    assert load_kw[10] == 0.0                   # EV charger finished at 05:00
    assert abs(load_kw[42] - 1.8) < 1e-9        # dishwasher alone at 21:00
    assert abs(load_kw[43] - 3.8) < 1e-9        # dishwasher + washing machine at 21:30


def test_no_schedule_means_no_flexible_load():
    assert scheduled_load_kw(EXAMPLE, None) == [0.0] * 48
    assert scheduled_load_kw(EXAMPLE, []) == [0.0] * 48
    plain = [row["demand_kw"] for row in run_day(EXAMPLE)]
    empty = [row["demand_kw"] for row in run_day(EXAMPLE, [])]
    assert plain == empty


def test_wrong_length_schedule_is_rejected():
    try:
        run_day(EXAMPLE, [43, 42])
    except ValueError:
        return
    assert False, "a schedule with the wrong number of start slots should raise ValueError"


def test_demand_includes_the_schedule():
    rows = run_day(EXAMPLE, BEST)
    assert abs(rows[4]["demand_kw"] - 7.3) < 1e-9       # base 0.3 + EV 7.0
    assert abs(rows[6]["demand_kw"] - 10.3) < 1e-9      # base 0.3 + EV 7.0 + immersion 3.0


def test_supply_guard_rule_vetoes_grid_charging():
    facts, fired = forward_chain(
        {"tariff_night", "has_battery", "battery_below_night_target", "at_supply_limit"}, RULES)
    assert "charge_battery_grid" in facts
    assert "block_grid_charging" in facts
    assert any(name == "supply_guard" for name, _, _ in fired)


def test_grid_charging_never_breaks_supply_limit():
    kb = load("restricted_supply")
    limit = kb["graph"]["home"]["supply_limit_kw"]
    rows = run_day(kb, EV_AT_MIDNIGHT)
    for row in rows:
        assert row["grid_import_kw"] <= limit + 1e-9
    # 00:00: EV 7.0 + base 0.3 leaves 0.7 kW spare, so the battery charges slowly
    assert rows[0]["battery_action"] == "charge_grid"
    added = rows[0]["soc_kwh"] - kb["graph"]["battery"]["initial_charge_kwh"]
    assert 0 < added < 0.7 * SLOT_HOURS + 1e-9


def test_no_grid_charging_at_the_supply_limit():
    kb = load("restricted_supply")
    kb["graph"]["home"]["supply_limit_kw"] = 7.3      # exactly what the home draws at 00:00
    row = run_day(kb, EV_AT_MIDNIGHT)[0]
    assert row["battery_action"] is None
    assert row["soc_kwh"] == kb["graph"]["battery"]["initial_charge_kwh"]
    assert any(name == "supply_guard" for name, _ in row["why"])


def test_discharge_covers_only_what_the_grid_would_supply():
    previous = EXAMPLE["graph"]["battery"]["initial_charge_kwh"]
    efficiency = EXAMPLE["graph"]["battery"]["efficiency"]
    for row in run_day(EXAMPLE, BEST):
        if row["battery_action"] == "discharge":
            solar = hourly_value(EXAMPLE, "solar", row["slot"])
            need_kwh = max(0.0, row["demand_kw"] - solar) * SLOT_HOURS
            delivered_kwh = (previous - row["soc_kwh"]) * efficiency
            assert delivered_kwh <= need_kwh + 0.01      # 0.01 allows for rounding of soc
            assert row["grid_import_kw"] >= 0
        previous = row["soc_kwh"]


def test_schedule_works_in_every_scenario():
    for name in ["example", "no_solar_battery", "high_solar", "restricted_supply"]:
        kb = load(name)
        problem = make_problem(kb)
        earliest = [domain[0] for domain in problem["domains"]]
        rows = run_day(kb, earliest)
        assert len(rows) == 48
        battery = kb["graph"].get("battery")
        for row in rows:
            if battery:
                assert battery["min_charge_kwh"] <= row["soc_kwh"] <= battery["capacity_kwh"]
            else:
                assert row["battery_action"] is None


if __name__ == "__main__":
    tests = [t for name, t in sorted(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print("PASS", t.__name__)
    print(len(tests), "tests passed")