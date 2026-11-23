#Importing libraries
import math
import random 


#importing queries from knowledge base
from src.knowledge_base import (
    query_graph, 
    appliances_of_type,
    price, hourly_value, 
    SLOTS_PER_DAY, 
    load_knowledge_base)

#Since the day is 48slots of 30mins, 1hr is 1.0, 30mins is 0.5
SLOTS_HOURS = 0.5 

#Money measured in euros, 1 = 1E
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


def problem(kb):
    """Gathering everything here into one dictionary so that the function stays quick"""
    
    graph = kb["graph"]
    
    names = appliances_of_type(kb, "FlexibleAppliances")