import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.knowledge_base import load_knowledge_base
from src.csp import make_problem
from src.localsearch import (
    random_state,
    cost,
    generate_neighbours,
    hill_climbing,
    random_restarting_hillclimbing,
    simulated_annealing
)

KB = load_knowledge_base(os.path.join(ROOT, "data", "scenarios", "example"))
PROBLEM = make_problem(KB)

BEST = [43, 42, 6, 4]
BEST_COST = 9.816

def test_random_state():
    random.seed(1)
    # Generate 50 scedhules to check if they are valid
    for i in range(50):
        state = random_state(PROBLEM)
        
        if len(state) != len(PROBLEM['names']):
            raise AssertionError("Wrong number of appliances")
        
        # checking if every appliance starts at its allowed window
        for j in range(len(state)):
            if state[j] not in PROBLEM["domains"][j]:
                raise AssertionError("Appliance is outside its time window")
        

def test_cost():
    result = cost(PROBLEM, BEST)

    #Checking if the cost matches my expexcted best value
    if round(result, 3) != BEST_COST:
        raise AssertionError("Best schedule cost is incorrect")
    
    
def test_quiet_hours_costs_more():
    # Move the dishwasher to 05:00, which is inside quiet hours
    noisy = [43, 10, 6, 4]

    # calculate the cost of both schedules
    noisy_cost = cost(PROBLEM, noisy)
    best_cost = cost(PROBLEM, BEST)

    # Check that running a noisy appliance during quiet hours adds a penalty
    if noisy_cost <= best_cost + 10:
        raise AssertionError("Quiet hours penalty is not working")
    
    

def test_change_exactly_one_appliance():
    # Generate all neighbours of the best schedule
    neighbours = generate_neighbours(PROBLEM, BEST)

    for neighbour in neighbours:
        changes = 0

        # count how many appliances have different starting times
        for i in range(len(BEST)):
            if neighbour[i] != BEST[i]:
                changes += 1

        #only one appliance should change per neighbour
        if changes != 1:
            raise AssertionError("Neighbour should change one appliance")
        

def test_hill_climbing_never_returns_a_worse_schedule():
    # Test hill climbing with 20 different starting schedules
    for seed in range(20):
        random.seed(seed)

        start = random_state(PROBLEM)
        result = hill_climbing(PROBLEM, start)

