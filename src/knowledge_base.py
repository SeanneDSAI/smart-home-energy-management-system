"""
Knowledge base: stores and retrieves the facts the system reasons over.

CONVENTIONS
  - The day is 48 slots of 30 minutes. Slot 0 = 00:00, slot 15 = 07:30, slot 47 = 23:30.
  - Times are "HH:MM" on the hour or half hour. "24:00" means end of day.
  - Time ranges are [start, end) and wrap past midnight: ["23:00", "07:00"] is overnight.
  - Run times round UP to whole slots (50 minutes -> 2 slots).
  - Slot numbers past 47 wrap round (48 -> 0) in price, hourly_value and facts_at.

INPUT: a scenario folder holding four JSON files
  appliances.json  list of appliances, each with:
      name              unique; "home" and "battery" are reserved
      power_kw          power draw while running (must be > 0)
      duration_minutes  how long one run takes
      flexible          true  -> also needs earliest (first start time) and
                                 latest_finish (time it must be done by)
                        false -> also needs start (fixed start time)
      noisy             optional, default false; noisy appliances are kept out of quiet hours
  tariff.json
      periods                  list of {name, times: [[start, end], ...], price_eur_per_kwh};
                               together they must cover every slot exactly once
      carbon_g_per_kwh_hourly  24 hourly grid carbon values (g CO2 per kWh)
  occupancy.json
      home   list of [start, end] when someone is home
      quiet  list of [start, end] quiet hours
  home.json
      supply_limit_kw      maximum total load from the grid
      base_load_kw_hourly  24 hourly values for always-on load (fridge, lights...)
      solar_kw_hourly      optional, 24 hourly solar output values (missing -> no solar)
      battery              optional: capacity_kwh, max_charge_kw, max_discharge_kw,
                           initial_charge_kwh, min_charge_kwh, efficiency (0-1)

OUTPUT: load_knowledge_base(folder) returns a dict
  graph      knowledge graph, {entity: {relationship: value}}
               "FlexibleAppliance" / "FixedAppliance"  -> is_a "Appliance"
               each appliance -> is_a, power_kw, duration_slots, noisy, and either
                                 earliest_slot + latest_finish_slot (flexible) or start_slot (fixed)
               "home"         -> is_a "Home", supply_limit_kw
               "battery"      -> is_a "Battery", plus the battery fields above (only if present)
  tariff     list of 48 period names, one per slot, e.g. tariff[34] == "peak"
  prices     {period name: EUR per kWh}
  occupied   set of slots when someone is home
  quiet      set of slots in quiet hours
  carbon     24 hourly values (g CO2 per kWh)
  solar      24 hourly values (kW), all 0 if the house has no solar
  base_load  24 hourly values (kW)

QUERIES
  query_graph(graph, entity, relationship)  -> value, or None if unknown
  appliances_of_type(kb, "FlexibleAppliance" or "FixedAppliance")  -> list of names
  price(kb, slot)                    -> EUR per kWh in that slot
  hourly_value(kb, "carbon" / "solar" / "base_load", slot)  -> value for that slot's hour
  facts_at(kb, slot)                 -> set of facts for the rule engine:
        tariff_night / tariff_day / tariff_peak, occupied, quiet_hours,
        solar_generating, has_battery
  time_to_slot("07:30") -> 15,  slot_to_time(15) -> "07:30"
  describe_kb(kb)                    -> readable summary (python -m src.knowledge_base)
"""

import json
import os
import math

SLOTS_PER_DAY = 48


def time_to_slot(hhmm):
    """'07:30' -> 15. '24:00' means end of day (slot 0).
    Rejects anything that is not HH:MM on the hour or half hour."""
    parts = hhmm.split(":")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        raise ValueError("Bad time '" + hhmm + "', expected HH:MM")
    hours, minutes = int(parts[0]), int(parts[1])
    if hours > 24 or minutes not in (0, 30) or (hours == 24 and minutes != 0):
        raise ValueError("Bad time '" + hhmm + "', must be on the hour or half hour, 00:00-24:00")
    return (hours * 2 + minutes // 30) % SLOTS_PER_DAY


def slot_to_time(slot):
    """15 -> '07:30'. Inverse of time_to_slot (slot 48 wraps to '00:00')."""
    slot = slot % SLOTS_PER_DAY
    return "%02d:%02d" % (slot // 2, (slot % 2) * 30)


def slots_between(start, end):
    """Slots from start up to (not including) end, wrapping past midnight."""
    slot, last = time_to_slot(start), time_to_slot(end)
    slots = [slot]
    while (slot + 1) % SLOTS_PER_DAY != last:
        slot = (slot + 1) % SLOTS_PER_DAY
        slots.append(slot)
    return slots


def load_knowledge_base(folder):
    """Read the four JSON files in a scenario folder and build the KB."""
    data = {}
    for name in ("appliances", "tariff", "occupancy", "home"):
        with open(os.path.join(folder, name + ".json")) as file:
            data[name] = json.load(file)

    # Knowledge graph: class hierarchy, then appliances, home and battery
    graph = {"FlexibleAppliance": {"is_a": "Appliance"},
             "FixedAppliance": {"is_a": "Appliance"}}
    for item in data["appliances"]:
        if item["power_kw"] <= 0:
            raise ValueError(item["name"] + ": power must be positive")
        entity = {"power_kw": item["power_kw"],
                  "duration_slots": math.ceil(item["duration_minutes"] / 30),
                  "noisy": item.get("noisy", False)}
        if item["flexible"]:
            entity["is_a"] = "FlexibleAppliance"
            entity["earliest_slot"] = time_to_slot(item["earliest"])
            entity["latest_finish_slot"] = time_to_slot(item["latest_finish"])
        else:
            entity["is_a"] = "FixedAppliance"
            entity["start_slot"] = time_to_slot(item["start"])
        if item["name"] in graph or item["name"] in ("home", "battery"):
            raise ValueError("Duplicate or reserved appliance name: " + item["name"])
        graph[item["name"]] = entity

    home = data["home"]
    graph["home"] = {"is_a": "Home", "supply_limit_kw": home["supply_limit_kw"]}
    if "battery" in home:
        graph["battery"] = home["battery"]
        graph["battery"]["is_a"] = "Battery"

    # Tariff timetable
    tariff = [None] * SLOTS_PER_DAY
    for period in data["tariff"]["periods"]:
        for start, end in period["times"]:
            for slot in slots_between(start, end):
                if tariff[slot] is not None:
                    raise ValueError("Two tariff periods overlap at slot " + str(slot))
                tariff[slot] = period["name"]
    if None in tariff:
        raise ValueError("Tariff does not cover slot " + str(tariff.index(None)))

    occupied, quiet = set(), set()
    for start, end in data["occupancy"]["home"]:
        occupied.update(slots_between(start, end))
    for start, end in data["occupancy"]["quiet"]:
        quiet.update(slots_between(start, end))

    return {"graph": graph, "tariff": tariff, "occupied": occupied, "quiet": quiet,
            "prices": {p["name"]: p["price_eur_per_kwh"] for p in data["tariff"]["periods"]},
            "carbon": data["tariff"]["carbon_g_per_kwh_hourly"],   # all these are 24 hourly values
            "solar": home.get("solar_kw_hourly", [0] * 24),        
            "base_load": home["base_load_kw_hourly"]}              


#  queries 

def query_graph(graph, entity, relationship):
    """Return the related value or None """
    return graph.get(entity, {}).get(relationship)


def appliances_of_type(kb, appliance_type):
    """Names of all 'FlexibleAppliance' or 'FixedAppliance'.
    Raises ValueError for any other type, so a typo fails loudly instead of returning []."""
    graph = kb["graph"]
    if query_graph(graph, appliance_type, "is_a") != "Appliance":
        known = sorted(n for n, edges in graph.items() if edges.get("is_a") == "Appliance")
        raise ValueError("Unknown appliance type '" + str(appliance_type) + "', expected one of " + str(known))
    return [name for name, edges in graph.items() if edges.get("is_a") == appliance_type]


def price(kb, slot):
    slot = slot % SLOTS_PER_DAY  # slot 48 -> 0, so runs past midnight work
    return kb["prices"][kb["tariff"][slot]]


def hourly_value(kb, profile, slot):
    """carbon, solar or base_load for a slot (two slots per hour)."""
    slot = slot % SLOTS_PER_DAY
    return kb[profile][slot // 2]


def facts_at(kb, slot):
    """Facts true at one slot, as strings for forward chaining."""
    slot = slot % SLOTS_PER_DAY
    facts = {"tariff_" + kb["tariff"][slot]}
    if slot in kb["occupied"]:
        facts.add("occupied")
    if slot in kb["quiet"]:
        facts.add("quiet_hours")
    if hourly_value(kb, "solar", slot) > 0:
        facts.add("solar_generating")
    if "battery" in kb["graph"]:
        facts.add("has_battery")
    return facts


def _slot_ranges(slots):
    """Group slot numbers into 'HH:MM-HH:MM' ranges, joining runs that cross midnight."""
    slots = sorted(set(s % SLOTS_PER_DAY for s in slots))
    if not slots:
        return "none"
    if len(slots) == SLOTS_PER_DAY:
        return "all day"
    runs = []
    for slot in slots:
        if runs and slot == runs[-1][1] + 1:
            runs[-1][1] = slot
        else:
            runs.append([slot, slot])
    if len(runs) > 1 and runs[0][0] == 0 and runs[-1][1] == SLOTS_PER_DAY - 1:
        runs[0][0] = runs.pop()[0]   # e.g. 23:00-24:00 + 00:00-07:00 -> 23:00-07:00
    return ", ".join(slot_to_time(a) + "-" + slot_to_time(b + 1) for a, b in runs)


def describe_kb(kb):
    """Readable summary of everything in the knowledge base, for the CLI, dashboard or demos."""
    graph = kb["graph"]
    lines = ["House", "  Supply limit: " + str(query_graph(graph, "home", "supply_limit_kw")) + " kW"]

    lines.append("Appliances")
    for name in appliances_of_type(kb, "FlexibleAppliance"):
        e = graph[name]
        lines.append("  %-17s %4.1f kW  %3d min  flexible, start from %s, done by %s%s" % (
            name, e["power_kw"], e["duration_slots"] * 30, slot_to_time(e["earliest_slot"]),
            slot_to_time(e["latest_finish_slot"]), ", noisy" if e["noisy"] else ""))
    for name in appliances_of_type(kb, "FixedAppliance"):
        e = graph[name]
        lines.append("  %-17s %4.1f kW  %3d min  fixed, starts at %s%s" % (
            name, e["power_kw"], e["duration_slots"] * 30, slot_to_time(e["start_slot"]),
            ", noisy" if e["noisy"] else ""))

    lines.append("Tariff")
    for period, cost in kb["prices"].items():
        slots = [s for s in range(SLOTS_PER_DAY) if kb["tariff"][s] == period]
        lines.append("  %-6s EUR %.2f/kWh  %s" % (period, cost, _slot_ranges(slots)))

    lines.append("Occupancy")
    lines.append("  Home:        " + _slot_ranges(kb["occupied"]))
    lines.append("  Quiet hours: " + _slot_ranges(kb["quiet"]))

    lines.append("Solar")
    if any(kb["solar"]):
        peak = max(range(24), key=lambda h: kb["solar"][h])
        lines.append("  %.1f kWh over the day, peak %.1f kW at %02d:00" % (
            sum(kb["solar"]), kb["solar"][peak], peak))
    else:
        lines.append("  none")

    lines.append("Battery")
    battery = graph.get("battery")
    if battery:
        lines.append("  %.1f kWh capacity, starts at %.1f kWh, keeps %.1f kWh in reserve" % (
            battery["capacity_kwh"], battery["initial_charge_kwh"], battery["min_charge_kwh"]))
        lines.append("  charge %.1f kW / discharge %.1f kW, %d%% efficient" % (
            battery["max_charge_kw"], battery["max_discharge_kw"], round(battery["efficiency"] * 100)))
    else:
        lines.append("  none")
    return "\n".join(lines)


if __name__ == "__main__":
    # python -m src.knowledge_base [scenario folder]
    import sys
    folder = sys.argv[1] if len(sys.argv) > 1 else os.path.join("data", "scenarios", "example")
    print(describe_kb(load_knowledge_base(folder)))
