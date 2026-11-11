# Smart Home Energy Management System — Project Proposal

**Module:** AINL3001 Knowledge-Driven AI
**Group:** Dream Team Wallahi

## Team Information

| Name | Student Number | GitHub Username |
|------|----------------|-----------------|
| Arshdip Chera | C24385641 | AshACxx |
| Seanne Oriemo | C24384533 | SeanneDSAI |
| Alex Rolff | C24319666 | roflalex |
| Karl Ypil | C24383681 | Kpil06 |
| Allen Lapitan | C24383676 | lentenamen |
| Dillon Thornton | C24452624 | dillon329 |

## Problem Description

Households lose money and energy because appliances run without regard to electricity tariffs, solar generation, or whether anyone is home. Irish electricity now uses time-of-use pricing (day, night, peak), so the same wash cycle can cost very different amounts depending on when it runs. Coordinating this by hand across several appliances is tedious and easy to get wrong.

Our Smart Home Energy Management System (SHEMS) decides **when and whether to run flexible appliances** (dishwasher, washing machine, EV charger, immersion heater) and **how to use a home battery**, so that electricity cost and carbon are reduced while respecting the household's comfort and deadline preferences and the limits of the home's electrical supply.

## Proposed AI Approach

The problem is knowledge-driven and combines several techniques from the module:

- **Constraint Satisfaction (CSP):** place each flexible appliance into time slots subject to constraints: task deadlines (e.g. laundry finished by 7am), total load staying under the main supply limit, and user "do not disturb" windows.
- **Local search / optimisation:** search over feasible schedules to minimise an objective (cost under the tariff, weighted by carbon), using hill-climbing or simulated annealing when many valid schedules exist.
- **Rule-based reasoning (expert system):** real-time control rules, for example "if tariff = peak and battery charge > 50%, discharge battery", or "if solar surplus and EV connected, charge EV".
- **Knowledge representation:** a knowledge base of facts about devices (power draw, flexibility, deadlines), the tariff calendar, and home occupancy, queried by the reasoner.

## System Design

Following the AIMA structured approach, the system is defined as:

- **Problem formulation:** choose on / off / defer actions for each flexible device across a 24-hour horizon of time slots.
- **State representation:** the planned on/off state of every device in every slot, plus the battery charge level.
- **Actions:** turn a device on, off, or defer it to a later slot; charge or discharge the battery.
- **Goal condition:** every task completed within its deadline and comfort window, with total load never exceeding the supply limit.
- **Knowledge representation:** device, tariff and occupancy facts plus control rules held in a knowledge base.
- **Reasoning mechanism:** constraint propagation to prune infeasible schedules, local search to select the cheapest feasible one, and forward-chaining rules for live control decisions.

Architecture: an input layer (device, tariff and preference data) feeds the knowledge base, which drives a CSP/search scheduler and a rule-based controller, producing a schedule and recommended actions through a command-line tool or simple dashboard. Components will reuse and extend the AIMA-inspired search and problem classes from the lab exercises.

## Planned Contributions

The project breaks into the following roles. The team will assign members to these before submission.

- Knowledge base and data model (devices, power draw, tariff calendar, occupancy)
- CSP scheduler and search
- Rule-based controller (expert system)
- Local search / optimisation of schedules
- Testing, evaluation and example scenarios
- Integration, dashboard/CLI, README and documentation

Roles will overlap in the code, so these describe who leads each part rather than strict boundaries. Progress will be tracked through regular GitHub commits.
