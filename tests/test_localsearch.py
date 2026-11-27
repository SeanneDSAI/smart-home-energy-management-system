"""
Unit tests for src/localsearch.py.
Run from the repository root:
    python tests/test_localsearch.py
"""

import os
import sys
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.knowledge_base import load_knowledge_base
from src.csp import make_problem
from src.localsearch import random_state

# Load the example household scenario
KB = load_knowledge_base(os.path.join(ROOT, "data", "scenarios", "example"))

# Create the scheduling problem
PROBLEM = make_problem(KB)


# Test that every appliance is assigned a starting slot
def test_random_state_length():
    state = random_state(PROBLEM)

    assert len(state) == len(PROBLEM["names"])


# Test that randomly generated start times belong to each appliance's domain
def test_random_state_domains():
    state = random_state(PROBLEM)

    for i in range(len(state)):
        assert state[i] in PROBLEM["domains"][i]


# Test that multiple random schedules stay with their domains
def test_multiple_random_states():
    random.seed(42)

    for _ in range(20):
        state = random_state(PROBLEM)

    assert len(state) == len(PROBLEM["names"])

    for i in range(len(state)):
        assert state[i] in PROBLEM["domains"][i]


if __name__ == "__main__":
    tests = [test for name, test in sorted (globals().items()) 
            if name.startswith("test_")]

    for test in tests:
        test()
        print("PASS", test.__name__)

    print(len(tests), "tests passed")

    

