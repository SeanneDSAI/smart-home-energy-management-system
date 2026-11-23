"""
Rule-based controller for SHEMS: the expert-system part.

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
# Antecedents use the facts from knowledge_base.facts_at(kb, slot):
#   tariff_night / tariff_day / tariff_peak, occupied, quiet_hours,
#   solar_generating, has_battery
# plus three dynamic facts the controller adds each slot from the live battery
# state of charge:
#   battery_has_charge          (above the reserve   -> it CAN discharge)
#   battery_has_room            (below the capacity  -> solar CAN top it up)
#   battery_below_night_target  (below the overnight target, e.g. 70% -> grid-charge
#                                at night, leaving room for tomorrow's free solar)
#
# The three battery actions are mutually exclusive by tariff band (a slot is
# exactly one of night / day / peak), so the battery never both charges and
# discharges in the same slot.
# ---------------------------------------------------------------------------
RULES = [
    Rule("peak_discharge",
         frozenset({"tariff_peak", "has_battery", "battery_has_charge"}),
         "discharge_battery",
         "peak price and the battery has usable charge"),

    Rule("night_charge",
         frozenset({"tariff_night", "has_battery", "battery_below_night_target"}),
         "charge_battery_grid",
         "cheap night rate and the battery is below its overnight target (room kept for tomorrow's solar)"),

    Rule("solar_charge",
         frozenset({"tariff_day", "solar_generating", "has_battery", "battery_has_room"}),
         "charge_battery_solar",
         "free solar is available and there is room in the battery"),

    Rule("peak_defer",
         frozenset({"tariff_peak"}),
         "avoid_starting_appliances",
         "peak price now, so do not start flexible appliances"),

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