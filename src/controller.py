"""
Controller: run the rule-based expert system across the whole day.

For each of the 48 half-hour slots it:
  1. gets the static facts from the knowledge base (facts_at),
  2. adds the dynamic battery facts from the tracked state of charge,
  3. runs forward chaining (rules.forward_chain),
  4. applies the chosen battery action and updates the state of charge,
  5. records what happened and why.

Run a quick manual check with:  python src/controller.py
"""

import os
import sys

# Put the repository root on the path so "from src.x import ..." resolves -
# the same convention the tests use. Works run from the root or on its own.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.knowledge_base import load_knowledge_base, facts_at, SLOTS_PER_DAY
from src.rules import RULES, forward_chain

SLOT_HOURS = 0.5   # each slot is half an hour, so energy (kWh) = power (kW) * 0.5
NIGHT_CHARGE_TARGET = 0.7   # charge only to this fraction overnight, leaving room for next-day solar


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

        # dynamic facts from the live state of charge
        if battery and soc > reserve + 1e-9:
            facts.add("battery_has_charge")
        if battery and soc < capacity - 1e-9:
            facts.add("battery_has_room")
        if battery and soc < night_target - 1e-9:
            facts.add("battery_below_night_target")

        facts, fired = forward_chain(facts, RULES)

        # apply at most one battery action this slot and update the charge
        action = None
        if "discharge_battery" in facts:
            delivered = min(max_discharge * SLOT_HOURS, soc - reserve)
            soc -= delivered
            action = "discharge"
        elif "charge_battery_grid" in facts or "charge_battery_solar" in facts:
            added = min(max_charge * SLOT_HOURS * efficiency, capacity - soc)
            soc += added
            action = "charge_solar" if "charge_battery_solar" in facts else "charge_grid"

        advice = [f for f in ("avoid_starting_appliances", "no_noisy_appliances") if f in facts]

        log.append({
            "slot": slot,
            "soc_kwh": round(soc, 2),
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
        print(f"{hh:02d}:{mm}  soc={row['soc_kwh']:>5} kWh  {action:<12} {why}")


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    data = os.path.join(here, "..", "data", "scenarios", "example")
    print_day(load_knowledge_base(data))