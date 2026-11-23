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