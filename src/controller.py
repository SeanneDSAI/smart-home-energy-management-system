"""
Controller: run the rule-based expert system across the whole day.

For each of the 48 half-hour slots it:
  1. gets the static facts from the knowledge base (facts_at),
  2. works out the home's demand (including the optimised schedule, if given),
     the solar surplus and the spare supply for the slot,
  3. adds the dynamic battery / solar / supply facts,
  4. runs forward chaining (rules.forward_chain),
  5. applies the chosen battery action (bounded by demand, supply limit and losses),
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
from src.csp import make_problem, running_slots

SLOT_HOURS = 0.5   # each slot is half an hour, so energy (kWh) = power (kW) * 0.5
NIGHT_CHARGE_TARGET = 0.7   # charge only to this fraction overnight, leaving room for next-day solar


def household_demand_kw(kb, slot):
    """Background demand (kW): base load plus any FIXED appliance running this
    slot. The scheduled FLEXIBLE appliances come from scheduled_load_kw, which
    run_day adds on top when it is given a schedule."""
    kw = hourly_value(kb, "base_load", slot)
    for name in appliances_of_type(kb, "FixedAppliance"):
        entity = kb["graph"][name]
        start, duration = entity["start_slot"], entity["duration_slots"]
        if any((start + k) % SLOTS_PER_DAY == slot for k in range(duration)):
            kw += entity["power_kw"]
    return kw


def scheduled_load_kw(kb, schedule):
    """kW in every slot from the optimised schedule: each flexible appliance's
    power in each slot it runs. 'schedule' is a list of start slots in the order
    of make_problem(kb)["names"] - the format the CSP and local search return.
    None or an empty list means no flexible appliances are placed (all zeros)."""
    load = [0.0] * SLOTS_PER_DAY
    if not schedule:
        return load
    problem = make_problem(kb)
    if len(schedule) != len(problem["names"]):
        raise ValueError("schedule has %d start slots but the scenario has %d flexible "
                         "appliances" % (len(schedule), len(problem["names"])))
    for i, start in enumerate(schedule):
        for slot in running_slots(problem, i, start):
            load[slot] += problem["power"][i]
    return load


def run_day(kb, schedule=None):
    """Return a slot-by-slot log of the controller's decisions and reasons.

    schedule: optional list of start slots from the CSP / local search. When
    given, the scheduled appliances count towards demand, so the battery reacts
    to them and grid charging leaves room for them under the supply limit."""
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

    supply_limit = kb["graph"]["home"]["supply_limit_kw"]
    flexible_kw = scheduled_load_kw(kb, schedule)

    log = []
    for slot in range(SLOTS_PER_DAY):
        facts = set(facts_at(kb, slot))
        demand_kw = household_demand_kw(kb, slot) + flexible_kw[slot]
        solar_kw = hourly_value(kb, "solar", slot)
        grid_kw = max(0.0, demand_kw - solar_kw)        # import before the battery acts
        headroom_kw = max(0.0, supply_limit - grid_kw)  # spare supply left this slot

        # dynamic facts from the live state of charge, the real solar surplus
        # and the spare supply
        if battery and soc > reserve + 1e-9:
            facts.add("battery_has_charge")
        if battery and soc < capacity - 1e-9:
            facts.add("battery_has_room")
        if battery and soc < night_target - 1e-9:
            facts.add("battery_below_night_target")
        if solar_kw > demand_kw + 1e-9:
            facts.add("solar_surplus")
        if headroom_kw <= 1e-9:
            facts.add("at_supply_limit")

        facts, fired = forward_chain(facts, RULES)

        # apply at most one battery action this slot and update the stored charge
        action = None
        if "discharge_battery" in facts:
            # cover only what the grid would supply (demand minus solar), with losses
            want_kwh = min(max_discharge, grid_kw) * SLOT_HOURS
            delivered = min(want_kwh, (soc - reserve) * efficiency)
            if delivered > 1e-9:
                soc -= delivered / efficiency
                grid_kw -= delivered / SLOT_HOURS
                action = "discharge"
        elif "charge_battery_grid" in facts and "block_grid_charging" not in facts:
            # grid power at night, stopping exactly at the overnight target (no
            # overshoot), and never drawing more than the spare supply allows
            charge_kw = min(max_charge, headroom_kw)
            added = min(charge_kw * SLOT_HOURS * efficiency, max(0.0, night_target - soc))
            if added > 1e-9:
                soc += added
                grid_kw += added / efficiency / SLOT_HOURS
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
            "grid_import_kw": round(max(0.0, grid_kw), 3),   # after the battery acts
            "battery_action": action,
            "advice": advice,
            "why": [(name, because) for name, consequent, because in fired],
        })
    return log

def print_day(kb, schedule=None):
    """Readable summary for a quick check or the demo."""
    for row in run_day(kb, schedule):
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