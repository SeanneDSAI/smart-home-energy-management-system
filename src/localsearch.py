#Importing libraries
import math
import random 
import sys
import os

# importing queries from knowledge base

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.knowledge_base import (
    query_graph, 
    appliances_of_type,
    price, hourly_value, 
    SLOTS_PER_DAY, 
    load_knowledge_base)

# Since the day is 48slots of 30mins, 1hr is 1.0, 30mins is 0.5
SLOT_HOURS = 0.5 

# Money measured in euros, 1 = 1E
W_MONEY = 1.0
W_PENALTY = 10.0
W_CARBON = 0.000083 #In the EU carbon market, CO₂ trades at roughly €0.000083 per gram (based on the live Trading Economics EU Carbon Permits)

def time_slots(slot):
    """slot 1: 00:00, slot 15 = 07:30, slot 48 = 00:00"""
    
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
    may charge from 18:00 until 07:00), so we work with the
    LENGTH of the window rather than comparing slot numbers.
    """
    
    # the knowledge graph: every appliance, plus the home and battery
    graph = kb["graph"] 
    
    # Look up this appliance's facts in the knowledge graph (all in slot numbers)
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


def problem_a(kb):
    """Gathering everything here into one dictionary so that the function stays quick"""
    
    graph = kb["graph"]
    
    names = appliances_of_type(kb, "FlexibleAppliances")
    
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


def random_state(problem):
    """A random schedule (every appliance inside its time window)."""
    results = []
    
    for domain in problem["domains"]: # Loop through each domain
        value = random.choice(domain) # Pick a random value from the domain
        results.append(value) 
    
    return results
        
def cost(problem, state):
    """cost = money + carbon + penalty * violations"""

    # demand in every slot = background + the appliances we are scheduling
    demand = list(problem["background"])
    for i, start in enumerate(state):
        for step in range(problem["duration"][i]):
            demand[(start + step) % SLOTS_PER_DAY] += problem["power"][i]
    
    money = 0.0         # Total electricity cost
    carbon = 0.0        # Total carbon emissions
    violations = 0.0    # Total number of constraint violations

    # Loop through each time slot in the day
    for s in range(SLOTS_PER_DAY):
        # Calculate how much electricity is needed from the grid after using solar
        grid = max(0.0, demand[s] - problem["solar"][s])

        kwh = grid * SLOT_HOURS  # Convert power usage into kWh

        money += kwh * problem["price"][s]    # Add electricity cost
        carbon += kwh * problem["carbon"][s]  # Add carbon emissions

        # Check if electricity usage goes over the supply limit
        violations += max(0.0, grid - problem["supply_limit"])

    # Check if noisy appliances are running during quiet hours
    for i, start in enumerate(state):
        if problem["noisy"][i]:  # Check if the appliance is noisy
            for step in range(problem["duration"][i]):  # Loop through its running time
                # Check if the appliance runs during quiet hours
                if (start + step) % SLOTS_PER_DAY in problem["kb"]["quiet"]:
                    violations += 1.0  # Add a penalty for breaking quiet hours

    # Calculate the final score using cost, carbon emissions and penalties
    return W_MONEY * money + W_CARBON * carbon + W_PENALTY * violations



