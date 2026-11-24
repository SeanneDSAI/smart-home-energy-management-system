"""
CSP scheduler: decides WHEN each flexible appliance runs.

The day is modelled as a constraint satisfaction problem (CSP):
  Variables   : the flexible appliances (each one gets a start slot)
  Domains     : the start slots that respect the appliance's earliest
                start and deadline (taken from the knowledge base)
  Constraints : quiet hours  - a noisy appliance may not run in a quiet slot
                supply limit - the load from the grid may never go over the limit

Backtracking search (with MRV and forward checking) finds valid schedules.
A schedule is a list of start slots, one per appliance, in the same order
as problem["names"] - the same format the local search uses.

Quick check:  python src/csp.py
"""

import os
import sys

# Put the repository root on the path so "from src.x import ..." works
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.knowledge_base import (
    query_graph,
    appliances_of_type,
    price, hourly_value,
    SLOTS_PER_DAY,
    load_knowledge_base)

def time_slots(slot):
    """slot 0: 00:00, slot 15 = 07:30, slot 48 = 00:00"""
    
    #using % to return 0
    slot = slot % SLOTS_PER_DAY
    
    hours = slot//2
    
    if slot % 2 == 0:
        minutes = "00"
    else:
        minutes = "30"
        
    #:02d makes 7 = 07
    return f"{hours:02d}:{minutes}"


def start_times(kb, name):
    """
    Return every slot in which a flexible appliance may START.

    The appliance must start no earlier than earliest_slot and
    finish no later than latest_finish_slot.

    The window can wrap past midnight (for example an EV that
    may charge from 19:00 until 07:00), so we work with the
    LENGTH of the window rather than comparing slot numbers.
    """
    
    #the knowledge graph: every appliance, plus the home and battery
    graph = kb["graph"] 
    
    #Look up this appliance's facts in the knowledge graph (all in slot numbers)
    earliest = query_graph(graph, name, "earliest_slot") #first slot it may start
    latest_finish = query_graph(graph, name, "latest_finish_slot") #sslot by which it must be done
    duration = query_graph(graph, name, "duration_slots") #how many slots it runs for
    
    # Number of slots between earliest and latest finish.
    # A result of 0 means the window covers the whole day
    # (for example 00:00 to 24:00).
    
    window = (latest_finish - earliest) % SLOTS_PER_DAY #handles windows past midnight
    
    if window == 0: #0 -> 24 whole day
        window = SLOTS_PER_DAY
    
    if window < duration:
        raise ValueError(
            name + ": the time window is shorter than the run time"
        )
    
    # The last possible start leaves exactly 'duration' slots
    # before the deadline.

    starts = []

    for offset in range(window - duration + 1):
        starts.append((earliest + offset) % SLOTS_PER_DAY)

    return starts


def make_problem(kb):
    """Gathering everything here into one dictionary so that the function stays quick"""
    
    graph = kb["graph"]
    
    names = appliances_of_type(kb, "FlexibleAppliance")
    
        # Background load = base load + appliances that cannot move.

    background = [
        hourly_value(kb, "base_load", s)
        for s in range(SLOTS_PER_DAY)
    ]

    for name in appliances_of_type(kb, "FixedAppliance"):

        start = query_graph(graph, name, "start_slot")
        duration = query_graph(graph, name, "duration_slots")
        power = query_graph(graph, name, "power_kw")

        for step in range(duration):
            background[(start + step) % SLOTS_PER_DAY] += power

    problem = {
        "kb": kb,
        "names": names,
        "domains": [start_times(kb, name) for name in names],
        "power": [query_graph(graph, n, "power_kw") for n in names],
        "duration": [query_graph(graph, n, "duration_slots") for n in names],
        "noisy": [query_graph(graph, n, "noisy") for n in names],
        "supply_limit": query_graph(graph, "home", "supply_limit_kw"),
        "price": [price(kb, s) for s in range(SLOTS_PER_DAY)],
        "carbon": [hourly_value(kb, "carbon", s) for s in range(SLOTS_PER_DAY)],
        "solar": [hourly_value(kb, "solar", s) for s in range(SLOTS_PER_DAY)],
        "background": background,
    }

    return problem

# Constraints

def running_slots(problem, i, start):
    """The slots appliance number i runs in if it starts at 'start'."""
    slots = []
    for step in range(problem["duration"][i]):
        slots.append((start + step) % SLOTS_PER_DAY)   # % wraps past midnight
    return slots

def quiet_ok(problem,i,start):
    """Quiet-hours constraint: a noisy appliance may not run in a slot"""
    if not problem["noisy"][i]:
        return True 
    for slot in running_slots(problem,i,start):
        if slot in problem["kb"]["quiet"]:
            return False
    return True

def load_per_slot(problem,assignment):
    load = list(problem["background"])
    for i, start in assignment.items():
        for slot in running_slots(problem,i,start):
            load[slot] += problem["power"][i]
    return

def supply_ok(problem,assignment):
    load = load_per_slot(problem,assignment)
    for s in range(SLOTS_PER_DAY):
        grid = max(0.0,load[s] - problem["solar"][s])
        #1e-9 absorbs float rounding
        if grid > problem["supply_limit"] + 1e-9:
            return False
    return True

def is_valid(problem,schedule):
    for i,start in enumerate(schedule):
        if start not in problem["domains"][i]:
            return False
        if not quiet_ok(problem,i,start):
            return False
    return supply_ok(problem,dict(enumerate(schedule)))