"""
Unit tests for src/rules.py, with a full-day sanity check of src/controller.py.
Run from the repository root:
    python tests/test_rules.py        (or:  pytest tests/test_rules.py)
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.rules import RULES, forward_chain                 # noqa: E402
from src.knowledge_base import load_knowledge_base          # noqa: E402
from src.controller import run_day, household_demand_kw                          
# noqa: E402

KB = load_knowledge_base(os.path.join(ROOT, "data", "scenarios", "example"))


def test_peak_discharges_when_battery_has_charge():
    facts, fired = forward_chain({"tariff_peak", "has_battery", "battery_has_charge"}, RULES)
    assert "discharge_battery" in facts
    assert "avoid_starting_appliances" in facts          # peak_defer also fires
    assert "peak_discharge" in [name for name, _, _ in fired]


def test_peak_without_charge_does_not_discharge():
    facts, _ = forward_chain({"tariff_peak", "has_battery"}, RULES)   # no battery_has_charge
    assert "discharge_battery" not in facts


def test_night_charges_below_target():
    facts, _ = forward_chain({"tariff_night", "has_battery", "battery_below_night_target"}, RULES)
    assert "charge_battery_grid" in facts


def test_night_stops_once_at_target():
    # Room in the battery, but already at/above the overnight target -> do not grid-charge,
    # so there is headroom left for tomorrow's free solar.
    facts, _ = forward_chain({"tariff_night", "has_battery", "battery_has_room"}, RULES)
    assert "charge_battery_grid" not in facts


def test_solar_charges_when_surplus():
    facts, _ = forward_chain({"solar_surplus", "has_battery", "battery_has_room"}, RULES)
    assert "charge_battery_solar" in facts


def test_solar_needs_surplus_not_just_sun():
    # Sun is up but all of it is being used by the home (no surplus) -> do not charge.
    facts, _ = forward_chain({"solar_generating", "has_battery", "battery_has_room"}, RULES)
    assert "charge_battery_solar" not in facts


def test_quiet_hours_blocks_noisy_appliances():
    facts, _ = forward_chain({"quiet_hours"}, RULES)
    assert "no_noisy_appliances" in facts

def test_rules_chain_through_costly_period():
    # classify_peak concludes "costly_period"; other rules build on that conclusion.
    facts, fired = forward_chain({"tariff_peak", "occupied"}, RULES)
    assert "costly_period" in facts            # derived, not an input fact
    assert "reduce_usage_advice" in facts       # occupied_reduce depends on costly_period
    names = [name for name, _, _ in fired]
    assert names.index("classify_peak") < names.index("occupied_reduce")


def test_every_firing_has_an_explanation():
    _, fired = forward_chain({"tariff_peak", "has_battery", "battery_has_charge"}, RULES)
    assert fired and all(because for _, _, because in fired)

def test_full_day_uses_solar():
    # With the headroom tweak and surplus check, the solar rule must fire during the day.
    assert any(row["battery_action"] == "charge_solar" for row in run_day(KB))


def test_day_never_charges_and_discharges_in_same_slot():
    for row in run_day(KB):
        assert row["battery_action"] in (None, "discharge", "charge_grid", "charge_solar")


def test_state_of_charge_stays_within_limits():
    battery = KB["graph"]["battery"]
    for row in run_day(KB):
        assert battery["min_charge_kwh"] - 1e-6 <= row["soc_kwh"] <= battery["capacity_kwh"] + 1e-6

# Test household demand when no fixed appliances are running
def test_background_demand():
    demand = household_demand_kw(KB, 0)

    assert abs(demand - 0.3) < 1e-9


# Test household demand when the oven is running
def test_fixed_appliance_demand():
    assert abs(household_demand_kw(KB, 36) - 3.3) < 1e-9
    assert abs(household_demand_kw(KB, 37) - 3.3) < 1e-9


# Test that oven demand is removed after it finishes
def test_fixed_appliance_finished():
    demand = household_demand_kw(KB, 38)

    assert abs(demand - 0.7) < 1e-9


# Test that the controller produces results for all 48 slots
def test_controller_full_day():
    results = run_day(KB)

    assert len(results) == 48

    for i in range(len(results)):
        assert results[i]["slot"] == i

# Test that the battery charges from the grid at night
def test_night_grid_charging():
    results = run_day(KB)

    assert results[0]["battery_action"] == "charge_grid"
    assert results[0]["soc_kwh"] == 6.25


# Test that overnight charging stops at the target
def test_night_charge_target():
    results = run_day(KB)

    assert results[1]["soc_kwh"] == 7.0
    assert results[2]["battery_action"] is None
    assert results[2]["soc_kwh"] == 7.0


# Test that the battery discharges during peak hours
def test_peak_battery_discharge():
    results = run_day(KB)

    for row in results:
        if row["battery_action"] == "discharge":
            assert KB["tariff"][row["slot"]] == "peak"

    assert any(row["battery_action"] == "discharge"
               for row in results)


# Test that battery actions correctly change the stored energy
def test_battery_charge_changes():
    results = run_day(KB)

    previous = KB["graph"]["battery"]["initial_charge_kwh"]

    for row in results:
        current = row["soc_kwh"]
        action = row["battery_action"]

        if action == "charge_grid" or action == "charge_solar":
            assert current >= previous

        elif action == "discharge":
            assert current <= previous

        else:
            assert current == previous

        previous = current


# Test that the controller works without a battery
def test_controller_without_battery():
    kb = load_knowledge_base(
        os.path.join(ROOT, "data", "scenarios", "example")
    )

    del kb["graph"]["battery"]

    results = run_day(kb)

    assert len(results) == 48

    for row in results:
        assert row["battery_action"] is None
        assert row["soc_kwh"] == 0


if __name__ == "__main__":
    tests = [t for name, t in sorted(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print("PASS", t.__name__)
    print(len(tests), "tests passed")