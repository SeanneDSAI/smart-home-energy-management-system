"""
Controller: run the rule-based expert system across the whole day.

For each of the 48 half-hour slots it:
  1. gets the static facts from the knowledge base (facts_at),
  2. works out the home's demand and solar surplus for the slot,
  3. adds the dynamic battery / solar facts,
  4. runs forward chaining (rules.forward_chain),
  5. applies the chosen battery action (bounded by demand, headroom and losses),
  6. records what happened and why.

Run a quick manual check with:  python -m src.controller
"""

import os
import sys

# Put the repository root on the path so "from src.x import ..." resolves -
# the same convention the tests use. Works run from the root or on its own.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.knowledge_base import (load_knowledge_base, facts_at, SLOTS_PER_DAY,
                                hourly_value, appliances_of_type)
from src.rules import RULES, forward_chain

SLOT_HOURS = 0.5   # each slot is half an hour, so energy (kWh) = power (kW) * 0.5
NIGHT_CHARGE_TARGET = 0.7   # charge only to this fraction overnight, leaving room for next-day solar


def household_demand_kw(kb, slot):
    """Background demand (kW) the controller knows about: base load plus any FIXED
    appliance running this slot. The scheduled FLEXIBLE appliances are not added
    here - that is the optimiser's output and belongs to the integration step."""
    kw = hourly_value(kb, "base_load", slot)
    for name in appliances_of_type(kb, "FixedAppliance"):
        entity = kb["graph"][name]
        start, duration = entity["start_slot"], entity["duration_slots"]
        if any((start + k) % SLOTS_PER_DAY == slot for k in range(duration)):
            kw += entity["power_kw"]
    return kw