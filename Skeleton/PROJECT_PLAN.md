# Project Plan — Sridhar Precision Works Scheduler

## Implementation Sequence

> **Mission-number cross-reference**: day-to-day work is tracked as Missions 2–8 (a flat,
> conversational numbering). This document's Phase 0–6 structure maps as:
> Phase 0 = foundation (pre-Mission-2) · Phase 1 = Mission 2 · Phase 2 = Mission 3 ·
> Phase 3 = Mission 4 · Phase 4 = Mission 5 · Phase 5 = Mission 6 · Phase 6 = Mission 7.
> Mission 8 (tests/docs/polish) cuts across all phases rather than mapping to one.

### Phase 0: Foundation (Complete before coding)
**Goal**: Establish engineering foundation, get human approval on design.

- [x] Inspect assignment materials (docx read directly; no README/AGENTS.md exist as separate
      files — this plan and the sibling docs serve that purpose)
- [x] Create DOMAIN_MODEL.md (entities, constraints, ambiguities) — **revised 2026-08-25** to
      resolve contradictions with the assignment brief (2 shifts not 3, one grinder not two,
      trimmed machine roster, added POWER_CUT + planned maintenance, grinder/customer
      concentration facts encoded as generation constraints)
- [x] Create ECONOMICS.md (cost model) — **revised 2026-08-25** (roster match, generator cost)
- [x] Create ARCHITECTURE.md (system design) — **revised 2026-08-25** (roster match, localization
      note, disruption type list)
- [x] Create PROJECT_PLAN.md (this document)
- [ ] Create config/ directory with assumption files — **next, start of Mission 2**
- [x] **GATE: Human approval on design** — approved 2026-08-25 ("start everything from scratch")

---

### Phase 1: Data Model & Generation
**Goal**: Deterministic, realistic test data for all entities.
**Estimated effort**: Medium

#### Tasks
1. **Domain model classes** (`src/models/`)
   - Dataclasses for all entities in DOMAIN_MODEL.md
   - Enums for all type fields
   - Type hints and validation

2. **Configuration loading** (`src/data/load.py`)
   - YAML config parser
   - Validate config against expected schema

3. **Data generation** (`src/data/generate.py`)
   - 14 machines with realistic specs (from config)
   - 18–22 operators with shift assignments and qualifications
   - 6–8 customers across 3 tiers
   - ~25 orders with realistic routings (3–6 steps each)
   - Changeover matrix (material × machine type transitions)
   - Breakdown history for robustness scoring
   - **All deterministic with seed=42**

4. **Data validation**
   - All orders are physically completable within 14-day horizon
   - Operator coverage exists for all shifts
   - At least one qualified operator per machine type per shift

5. **Tests** (`tests/test_data/`)
   - Data generation produces consistent output
   - All constraints satisfiable
   - Routing steps reference valid machine types

#### Output
- `data/machines.json`, `data/operators.json`, `data/orders.json`, etc.
- All data files committed and reproducible

---

### Phase 2: Core Scheduler
**Goal**: Generate valid 2-week schedules for all three strategies.
**Estimated effort**: Large
**Depends on**: Phase 1

#### Tasks
1. **Schedule data structure** (`src/models/schedule.py`)
   - Schedule grid: 14 machines × 42 shifts
   - ScheduleSlot with full metadata

2. **Dispatching heuristics** (`src/scheduler/heuristics.py`)
   - Earliest Due Date (EDD)
   - Shortest Processing Time (SPT)
   - Weighted priority (tier × urgency × slack)

3. **Slot allocator** (`src/scheduler/slot_allocator.py`)
   - Find eligible (machine, shift, operator) tuples
   - Score by strategy objective
   - Handle changeover time insertion
   - Handle lot splitting across shifts

4. **Strategy implementations** (`src/scheduler/strategies.py`)
   - `CheapestStrategy`: Minimize cost → prefer day shifts, group changeovers, accept some tardiness
   - `OnTimeStrategy`: Minimize tardiness → EDD priority, allow overtime, high-tier first
   - `RobustStrategy`: Maximize slack → conservative loading (≤75%), prefer reliable machines

5. **Scheduling engine** (`src/scheduler/engine.py`)
   - Orchestrates strategy + allocator + validation
   - Produces complete Schedule object

6. **Tests** (`tests/test_scheduler/`)
   - Single-order scheduling correctness
   - Precedence constraint enforcement
   - Machine conflict prevention
   - Strategy produces distinct schedules
   - Edge cases: tight deadline, overloaded machines

#### Output
- Three complete, validated 2-week schedules
- Each schedule with cost breakdown

---

### Phase 3: Validation & Costing
**Goal**: Every schedule is provably feasible; every cost is traceable.
**Estimated effort**: Medium
**Depends on**: Phase 2

#### Tasks
1. **Constraint checker** (`src/validation/constraint_checker.py`)
   - HC-1 through HC-11 individual checkers
   - Clear error messages with slot IDs

2. **Feasibility validator** (`src/validation/feasibility.py`)
   - Runs all checkers
   - Returns structured pass/fail report

3. **Cost calculator** (`src/costing/calculator.py`)
   - Per-slot cost breakdown
   - Overtime detection and premium calculation
   - Changeover cost calculation
   - Late penalty calculation

4. **Strategy comparison** (`src/costing/comparison.py`)
   - Side-by-side metrics for all three strategies
   - Total cost, overtime hours, late orders, utilization %

5. **Tests** (`tests/test_validation/`, `tests/test_costing/`)
   - Known-infeasible schedules are rejected
   - Cost calculations match hand-calculated examples
   - Penalty caps are respected

---

### Phase 4: Disruption Replanning
**Goal**: Handle all four disruption types with explanations.
**Estimated effort**: Large
**Depends on**: Phase 3

#### Tasks
1. **Disruption event model** (`src/models/disruption.py`)
   - Four types: MACHINE_BREAKDOWN, OPERATOR_ABSENCE, MATERIAL_DELAY, REWORK_REQUIRED

2. **Replan engine** (`src/replanner/replan_engine.py`)
   - Freeze completed/in-progress work
   - Identify affected future slots
   - Re-dispatch affected operations
   - Calculate cost delta

3. **Explanation generator** (`src/replanner/explanation.py`)
   - Human-readable: "Machine CNC_VMC_01 broke down at 10:30 AM on Day 3. Moved ORD_005 Step 3 from CNC_VMC_01 Shift 2 to CNC_VMC_02 Shift 3. Added 45 min changeover. Cost increase: ₹2,340."

4. **Disruption scenarios** (from `config/disruption_scenarios.yaml`)
   - Pre-built scenarios covering all four types
   - Cascading disruption (breakdown + absence simultaneously)

5. **Tests** (`tests/test_replanner/`)
   - Completed work is never modified
   - Replanned schedule is feasible
   - Cost delta is correctly calculated
   - Explanations are generated for every change

---

### Phase 5: Dashboard & 6 AM View
**Goal**: Supervisor-friendly operational interface.
**Estimated effort**: Medium
**Depends on**: Phase 4

#### Tasks
1. **Web application** (`src/dashboard/app.py`)
   - Flask app with Jinja2 templates
   - Routes for dashboard, schedule views, disruption panel

2. **6 AM Morning View**
   - Today's machine-by-machine plan
   - At-risk orders (highlighted by tier)
   - Machine and operator status
   - Cost summary

3. **Schedule comparison view**
   - Side-by-side three strategies
   - Gantt chart (machine × time)
   - Cost breakdown tables

4. **Disruption panel**
   - Inject disruptions
   - View before/after schedule
   - Read explanation of changes

---

### Phase 6: Defense & Demo System
**Goal**: Handle live disruption scenarios in a presentation setting.
**Estimated effort**: Medium
**Depends on**: Phase 5

#### Tasks
1. **Interactive demo** (`src/defense/demo.py`)
   - CLI or web-based disruption injection
   - Real-time replanning and display
   - "What-if" scenario exploration

2. **Pre-built scenarios** (`src/defense/scenarios.py`)
   - 5–7 curated scenarios of increasing complexity
   - Each with expected outcomes documented

3. **Presentation aids**
   - Summary statistics
   - Key talking points per scenario
   - Cost impact visualization

---

## Milestones & Tags

| Milestone | Tag | Gate |
|-----------|-----|------|
| Foundation complete | `v0.0-foundation` | Human approval on design |
| Data generation working | `v0.1-data` | All data validates |
| Schedules generated | `v0.2-scheduler` | All three strategies produce valid schedules |
| Costs calculated | `v0.3-costing` | Costs match hand calculations |
| Replanning works | `v0.4-replan` | All four disruption types handled |
| Dashboard live | `v0.5-dashboard` | 6 AM view renders correctly |
| Demo ready | `v1.0-demo` | Full defense/demo capability |

---

## Items Requiring Human Approval Before Implementation

> [!IMPORTANT]
> The following decisions significantly affect implementation and should be confirmed before coding begins.

### Must-Approve

1. **Ambiguity resolutions (A-1 through A-10 in DOMAIN_MODEL.md)**
   - Especially: lot splitting, shift spanning, overtime limits, weekend inclusion

2. **Machine fleet** — Are the 14 proposed machines realistic for the scenario? Should any be swapped?

3. **Cost rates** — Are the INR rates in ECONOMICS.md reasonable? Any that need adjustment?

4. **Scheduling algorithm choice** — Heuristic dispatching vs. constraint programming solver. I propose heuristic for explainability; should we consider CP-SAT as alternative?

5. **Dashboard technology** — Flask server-rendered vs. interactive HTML with JavaScript?

### Nice-to-Confirm

6. **Customer tier penalty rates** — 2%/1%/0.5% per day — realistic?
7. **Overtime multiplier** — 1.5× then 2.0× (MSME practice) vs. straight 2.0× (strict law)?
8. **Number of orders** — ~25 orders good, or should it be higher/lower for a realistic 2-week load?
9. **Operator-to-machine ratio** — Should some CNC machines allow 1-operator-to-2-machines?

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Schedule infeasibility (too many orders for capacity) | High | Data generation validates feasibility; adjustable order count |
| Heuristic produces poor schedules | Medium | Multiple dispatching rules; compare against simple bounds |
| Changeover matrix too complex | Medium | Start with material-based categories, not full N×N matrix |
| Dashboard scope creep | Low | Minimal viable dashboard first; polish after core works |
| Replanning cascades infinitely | Medium | Limit replan iterations; validate after each pass |
