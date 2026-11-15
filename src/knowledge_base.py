"""
 knowledge base: stores and retrieves the facts the system reasons over.
The day is 48 slots of 30 minutes (slot 0 = 00:00)..
"""

import json
import os

SLOTS_PER_DAY = 48


def time_to_slot(hhmm):
    """'07:30' -> 15. '24:00' means end of day (slot 0)."""
    hours, minutes = hhmm.split(":")
    return (int(hours) * 2 + int(minutes) // 30) % SLOTS_PER_DAY


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
                  "duration_slots": item["duration_minutes"] // 30,
                  "noisy": item.get("noisy", False)}
        if item["flexible"]:
            entity["is_a"] = "FlexibleAppliance"
            entity["earliest_slot"] = time_to_slot(item["earliest"])
            entity["latest_finish_slot"] = time_to_slot(item["latest_finish"])
        else:
            entity["is_a"] = "FixedAppliance"
            entity["start_slot"] = time_to_slot(item["start"])
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
    """Names of all 'FlexibleAppliance' or 'FixedAppliance' """
    return [name for name, edges in kb["graph"].items() if edges.get("is_a") == appliance_type]


def price(kb, slot):
    return kb["prices"][kb["tariff"][slot]]


def hourly_value(kb, profile, slot):
    """carbon, solar or base_load for a slot (two slots per hour)."""
    return kb[profile][slot // 2]


def facts_at(kb, slot):
    """Facts true at one slot, as strings for forward chaining."""
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
