"""
Local search for SHEMS: find a cheap schedule for the flexible appliances.

A state is a list of start slots, one per appliance, each taken from that
appliance's CSP domain (src.csp.make_problem). The cost of a state is

    W_MONEY * money + W_CARBON * carbon + W_PENALTY * violations

where violations are grid draw above the supply limit plus noisy appliances
running in quiet hours. A neighbour moves ONE appliance to a different start.

Algorithms:
  - hill_climbing                     (steepest descent to a local minimum)
  - random_restarting_hillclimbing    (best of several random starts)
  - simulated_annealing               (bonus, for comparison)

Run a quick manual check from the repository root with:  python -m src.localsearch
"""

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
    load_knowledge_base
    )

from src.csp import time_slots, start_times, make_problem

# Since the day is 48slots of 30mins, 1hr is 1.0, 30mins is 0.5
SLOT_HOURS = 0.5 

# Money measured in euros, 1 = 1E
W_MONEY = 1.0
W_PENALTY = 10.0
W_CARBON = 0.000083 #In the EU carbon market, CO₂ trades at roughly €0.000083 per gram (based on the live Trading Economics EU Carbon Permits)





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


def generate_neighbours(problem, state):
    """Every schedule that moves ONE appliance to a different start slot.
        the point is to pick the cheapest slot for every appliance"""
    neighbours = []

    # Iterating through every state
    for i in range(len(state)):

        # Checking which slots the appliance can start at 
        for slot in problem["domains"][i]:
            #If the current slot is not equal to the neighoubour switch it with the new one
            if slot != state[i]:
                new_state = list(state)      # copy, so state is not changed
                new_state[i] = slot
                neighbours.append(new_state)
    return neighbours

def hill_climbing(problem, start_state):
    """
    Improve a schedule by repeatedly moving to its cheapest neighbour.
    Stops when no neighbour is cheaper (a local minimum).
    """
    
    current = start_state
    
    while True:
        neighbours = generate_neighbours(problem, current)
        
        best = current 
        best_cost = cost(problem, current)
        
        for neighbour in neighbours:
            neighbour_cost = cost(problem, neighbour)
            
            if neighbour_cost < best_cost:
                best = neighbour
                best_cost = neighbour_cost
        
        if best == current:
            return current
        
        current = best



def random_restarting_hillclimbing(problem, restarts = 20):
    best = None
    best_cost = float("inf")

    for _ in range (restarts):

        solution = hill_climbing(problem, random_state(problem))
        solution_cost  = cost(problem, solution)

        if solution_cost < best_cost:
            best = solution
            best_cost = solution_cost

    return best


#BONUS ALGORITHM ADDING ANNEALING FOR COMPARISON

START_TEMP = 0.5
COOLING = 0.95
STOP_TEMP = 0.001

def simulated_annealing(problem, start_state):
    """Sometimes accept a WORSE neighbour, less often as the temperature falls."""
    current = start_state
    best = current
    temp = START_TEMP

    while temp > STOP_TEMP:

        neighbours = generate_neighbours(problem, current)
        if not neighbours:
            return current      

        neighbour = random.choice(neighbours)
        delta = cost(problem, neighbour) - cost(problem, current)

        # always accept an improvement; accept a worse move with probability e^(-delta/T)
        if delta < 0 or random.random() < math.exp(-delta / temp):
            current = neighbour

        if cost(problem, current) < cost(problem, best):
            best = current

        temp = temp * COOLING

    return best






"""Quick check to see if program runs correctly"""

if __name__ == "__main__":
    from src.knowledge_base import load_knowledge_base

    
    kb = load_knowledge_base("data/scenarios/example")
    problem = make_problem(kb)


    start = random_state(problem)
    print("Start :", start, round(cost(problem, start), 3))
    
    for name, slot in zip(problem["names"], start):
        print(name, "starts at", time_slots(slot))
        print("\n")
    
    climbed = hill_climbing(problem, start)
    print("Hill  :", climbed, round(cost(problem, climbed), 3))

    best = random_restarting_hillclimbing(problem)
    print("Best  :", best, round(cost(problem, best), 3))