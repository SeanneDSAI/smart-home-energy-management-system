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
    
    for i in range(50):
        state = random_state(PROBLEM)
        
        if len(state) != len(PROBLEM['names']):
            raise AssertionError("Wrong number of appliances")
        
        for j in range(len(state)):
            if state[j] not in PROBLEM["domains"][j]:
                raise AssertionError("Appliance is outside its time window")
        

def test_cost():
    result = cost(PROBLEM, BEST)

    if round(result, 3) != BEST_COST:
        raise AssertionError("Best schedule cost is incorrect")