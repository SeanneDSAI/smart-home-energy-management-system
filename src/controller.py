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

def run_day(kb):
    """Return a slot-by-slot log of the controller's decisions and reasons."""
    battery = kb["graph"].get("battery")
    if battery:
        soc = battery["initial_charge_kwh"]
        capacity = battery["capacity_kwh"]
        reserve = battery["min_charge_kwh"]
        max_charge = battery["max_charge_kw"]
        max_discharge = battery["max_discharge_kw"]
        efficiency = battery.get("efficiency", 1.0)
        night_target = capacity * NIGHT_CHARGE_TARGET
    else:
        soc = capacity = reserve = max_charge = max_discharge = night_target = 0.0
        efficiency = 1.0

    log = []
    for slot in range(SLOTS_PER_DAY):
        facts = set(facts_at(kb, slot))
        demand_kw = household_demand_kw(kb, slot)
        solar_kw = hourly_value(kb, "solar", slot)

        # dynamic facts from the live state of charge and the real solar surplus
        if battery and soc > reserve + 1e-9:
            facts.add("battery_has_charge")
        if battery and soc < capacity - 1e-9:
            facts.add("battery_has_room")
        if battery and soc < night_target - 1e-9:
            facts.add("battery_below_night_target")
        if solar_kw > demand_kw + 1e-9:
            facts.add("solar_surplus")

        facts, fired = forward_chain(facts, RULES)

        # apply at most one battery action this slot and update the stored charge
        action = None
        if "discharge_battery" in facts:
            # cover the home's demand, no more, and account for discharge losses
            want_kwh = min(max_discharge, demand_kw) * SLOT_HOURS
            delivered = min(want_kwh, (soc - reserve) * efficiency)
            if delivered > 1e-9:
                soc -= delivered / efficiency
                action = "discharge"
        elif "charge_battery_grid" in facts:
            # grid power at night, stopping exactly at the overnight target (no overshoot)
            added = min(max_charge * SLOT_HOURS * efficiency, max(0.0, night_target - soc))
            if added > 1e-9:
                soc += added
                action = "charge_grid"
        elif "charge_battery_solar" in facts:
            # store only the spare solar (solar minus demand), with charge losses
            surplus_kwh = max(0.0, solar_kw - demand_kw) * SLOT_HOURS
            inflow = min(max_charge * SLOT_HOURS, surplus_kwh, (capacity - soc) / efficiency)
            added = inflow * efficiency
            if added > 1e-9:
                soc += added
                action = "charge_solar"

        advice = [f for f in ("avoid_starting_appliances", "no_noisy_appliances",
                              "reduce_usage_advice") if f in facts]

        log.append({
            "slot": slot,
            "soc_kwh": round(soc, 2),
            "demand_kw": round(demand_kw, 2),
            "battery_action": action,
            "advice": advice,
            "why": [(name, because) for name, consequent, because in fired],
        })
    return log

def print_day(kb):
    """Readable summary for a quick check or the demo."""
    for row in run_day(kb):
        if not row["battery_action"] and not row["advice"]:
            continue
        hh, mm = row["slot"] // 2, "30" if row["slot"] % 2 else "00"
        action = row["battery_action"] or "-"
        why = "; ".join(because for _, because in row["why"])
        print(f"{hh:02d}:{mm}  soc={row['soc_kwh']:>5} kWh  demand={row['demand_kw']:>4} kW  "
              f"{action:<12} {why}")


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    data = os.path.join(here, "..", "data", "scenarios", "example")
    print_day(load_knowledge_base(data))