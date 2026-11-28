"""
Rule-based controller for SHEMS: the expert-system part (Weeks 7-8).

Forward chaining over a SET of string facts, matching the facts produced by
knowledge_base.facts_at(kb, slot). A rule fires when all of its antecedents
are present; it then adds its consequent (a derived fact / action) and records
why it fired. This file reasons purely over facts, so it has no other imports.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    name: str
    antecedents: frozenset   # ALL must be present for the rule to fire
    consequent: str          # the fact / action added when it fires
    because: str             # plain-language explanation of the firing


def forward_chain(facts, rules):
    """
    Forward chaining (Weeks 7-8).

    facts : an iterable of string facts (the working memory for one slot)
    rules : the list of Rule objects (the knowledge base)

    Fire every rule whose antecedents are all present, add its consequent,
    and repeat until nothing new is added (a fixed point). A rule fires at
    most once, because once its consequent is already a fact it stops adding it.

    Because some rules add facts that other rules depend on (for example
    classify_peak adds "costly_period", which the peak rules then use), the
    reasoning can go several levels deep, not just one.

    Returns (closed_facts, fired), where `fired` is a list of
    (rule_name, consequent, because) explaining each firing - the Week 8
    "explanation" of the reasoning.
    """
    facts = set(facts)
    fired = []
    changed = True
    while changed:
        changed = False
        for rule in rules:
            if rule.consequent not in facts and rule.antecedents <= facts:
                facts.add(rule.consequent)
                fired.append((rule.name, rule.consequent, rule.because))
                changed = True
    return facts, fired


# ---------------------------------------------------------------------------
# The rule set.
#
# Base facts from knowledge_base.facts_at(kb, slot):
#   tariff_night / tariff_day / tariff_peak, occupied, quiet_hours,
#   solar_generating, has_battery
# Dynamic facts the controller adds each slot:
#   battery_has_charge          (above the reserve   -> it CAN discharge)
#   battery_has_room            (below the capacity  -> it CAN be topped up)
#   battery_below_night_target  (below the overnight target -> grid-charge at night)
#   solar_surplus               (solar output exceeds the home's demand right now)
# Derived fact (added by one rule and used by others -> real forward chaining):
#   costly_period               (concluded from tariff_peak; drives the peak rules)
#
# The battery never charges and discharges in the same slot: solar_surplus does
# not occur at peak in the data, and the controller applies discharge first.
# ---------------------------------------------------------------------------
RULES = [
    # Classify a peak slot once, then let several rules build on that conclusion.
    Rule("classify_peak",
         frozenset({"tariff_peak"}),
         "costly_period",
         "peak tariff, so importing now is costly"),

    Rule("peak_discharge",
         frozenset({"costly_period", "has_battery", "battery_has_charge"}),
         "discharge_battery",
         "costly period and the battery has usable charge"),

    Rule("peak_defer",
         frozenset({"costly_period"}),
         "avoid_starting_appliances",
         "costly period, so do not start flexible appliances"),

    Rule("occupied_reduce",
         frozenset({"costly_period", "occupied"}),
         "reduce_usage_advice",
         "someone is home during a costly period, so suggest cutting usage"),

    Rule("night_charge",
         frozenset({"tariff_night", "has_battery", "battery_below_night_target"}),
         "charge_battery_grid",
         "cheap night rate and the battery is below its overnight target (room kept for tomorrow's solar)"),

    Rule("solar_charge",
         frozenset({"solar_surplus", "has_battery", "battery_has_room"}),
         "charge_battery_solar",
         "spare solar beyond the home's demand, with room in the battery"),

     Rule("supply_guard",
          frozenset({"at_supply_limit"}),
          "block_grid_charging",
          "the home is already using its full supply, so do not charge from the grid"),

    Rule("quiet_no_noise",
         frozenset({"quiet_hours"}),
         "no_noisy_appliances",
         "quiet hours, so do not run noisy appliances"),
]


# Which derived fact means which physical battery action (used by the controller).
BATTERY_ACTIONS = {
    "discharge_battery": "discharge",
    "charge_battery_grid": "charge_grid",
    "charge_battery_solar": "charge_solar",
}