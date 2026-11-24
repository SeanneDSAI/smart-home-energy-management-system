# smart-home-enerygy-management-system
Knowledge-driven AI system that schedules home appliances and battery use to cut electricity cost and carbon under time-of-use tariffs.
<<<<<<< HEAD
=======

**Module:** AINL3001 Knowledge-Driven AI · **Group:** Dream Team Wallahi

SHEMS decides **when to run flexible appliances** (dishwasher, washing machine, EV charger, immersion heater) and **how to use a home battery**. It works across a 24-hour day split into 48 half-hour slots and respects:

- time-of-use electricity prices (night / day / peak)
- appliance deadlines (e.g. laundry done by 07:00)
- the home's main supply limit
- quiet hours for noisy appliances
- solar generation and home occupancy

See [proposal.md](proposal.md) for the full problem description and design.

## AI techniques

| Technique | File | Status |
|---|---|---|
| Knowledge representation (knowledge graph of devices, tariff, occupancy) | [src/knowledge_base.py](src/knowledge_base.py) | Done |
| Rule-based expert system (forward chaining with explanations) | [src/rules.py](src/rules.py) | Done |
| Slot-by-slot battery controller driven by the rules | [src/controller.py](src/controller.py) | Done |
| Constraint satisfaction: backtracking with MRV and forward checking | [src/csp.py](src/csp.py) | In progress |
| Local search: hill climbing / simulated annealing over cost + carbon | [src/localsearch.py](src/localsearch.py) | In progress |

## Requirements

- Python 3.10 or newer
- No third-party packages are needed to run the code. Everything uses the standard library.
- [pytest](https://pytest.org) is optional, for running the tests.

## Setup

```bash
git clone <https://github.com/SeanneDSAI/smart-home-energy-management-system>
cd smart-home-energy-management-system

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Usage

Run every command from the repository root.

**Summarise a scenario** (house, appliances, tariff, occupancy, solar and battery):

```bash
python -m src.knowledge_base                         # uses data/scenarios/example
python -m src.knowledge_base data/scenarios/<name>   # any other scenario
```

**Run the rule-based controller for a day.** This prints each slot where the battery acts or advice is given, with the reason:

```bash
python -m src.controller
```

Example output:

```text
00:00  soc= 6.25 kWh  demand= 0.3 kW  charge_grid  cheap night rate and the battery is below its overnight target ...
01:00  soc=  7.0 kWh  demand= 0.3 kW  -            quiet hours, so do not run noisy appliances
```

## Tests

```bash
python tests/test_knowledge_base.py
python tests/test_rules.py

# or, with pytest installed
pytest
```

## Project structure

```text
kdai_group/
├── data/
│   └── scenarios/
│       └── example/          # one scenario = four JSON files
│           ├── appliances.json
│           ├── home.json
│           ├── occupancy.json
│           └── tariff.json
├── src/
│   ├── knowledge_base.py     # loads scenarios, knowledge graph, queries, facts per slot
│   ├── rules.py              # rule set and forward chaining
│   ├── controller.py         # runs the rules across the day, manages the battery
│   ├── csp.py                # CSP scheduler for flexible appliances
│   └── localsearch.py        # cost + carbon optimisation
├── tests/
├── proposal.md
├── requirements.txt
└── README.md
```

## Scenario format

A scenario is a folder holding four JSON files. Times are `"HH:MM"` strings on the hour or half hour, from `00:00` to `24:00`. A time window can wrap past midnight, e.g. `"18:00"` to `"07:00"`.

**`appliances.json`** is a list of appliances, each either flexible or fixed:

```json
{ "name": "dishwasher", "power_kw": 1.8, "duration_minutes": 120,
  "flexible": true, "noisy": true, "earliest": "20:00", "latest_finish": "07:00" }

{ "name": "oven", "power_kw": 2.5, "duration_minutes": 60,
  "flexible": false, "start": "18:00" }
```

**`home.json`** holds the supply limit, a 24-value hourly base load, and optionally a 24-value hourly solar profile and a battery:

```json
{ "supply_limit_kw": 12.0,
  "base_load_kw_hourly": [0.3, 0.3, "... 24 values"],
  "solar_kw_hourly":     [0, 0, "... 24 values"],
  "battery": { "capacity_kwh": 10.0, "max_charge_kw": 5.0, "max_discharge_kw": 5.0,
               "initial_charge_kwh": 4.0, "min_charge_kwh": 1.0, "efficiency": 0.9 } }
```

**`occupancy.json`** lists the time ranges when someone is home and the quiet hours:

```json
{ "home":  [["00:00", "08:30"], ["17:30", "24:00"]],
  "quiet": [["23:00", "07:00"]] }
```

**`tariff.json`** holds the price periods, which must cover every slot exactly once, and a 24-value hourly carbon intensity:

```json
{ "periods": [
    { "name": "night", "times": [["23:00", "08:00"]], "price_eur_per_kwh": 0.18 },
    { "name": "day",   "times": [["08:00", "17:00"], ["19:00", "23:00"]], "price_eur_per_kwh": 0.34 },
    { "name": "peak",  "times": [["17:00", "19:00"]], "price_eur_per_kwh": 0.42 } ],
  "carbon_g_per_kwh_hourly": [220, 210, "... 24 values"] }
```

The example prices are illustrative and use the Irish smart time-of-use structure.

To add a scenario, copy `data/scenarios/example/` to a new folder and edit the files.

## Team

| Name | Role | GitHub |
|---|---|---|
| Dillon Thornton | Knowledge Base & Data Model | [dillon329](https://github.com/dillon329) |
| Alex Rolff | CSP Scheduler & Search | [roflalex](https://github.com/roflalex) |
| Seanne Oriemo | Rule-Based Controller | [SeanneDSAI](https://github.com/SeanneDSAI) |
| Arshdip Chera | Local Search & Optimisation | [AshACxx](https://github.com/AshACxx) |
| Karl Ypil | Testing & Evaluation | [Kpil06](https://github.com/Kpil06) |
| Allen Lapitan | Integration & Documentation | [lentenamen](https://github.com/lentenamen) |
>>>>>>> 6792b55 (updated setup instructions)
