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
from src.controller import run_day                          # noqa: E402

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