# Architecture — Sridhar Precision Works Scheduler

## 1. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         config/ (YAML)                               │
│   machines.yaml │ operators.yaml │ shifts.yaml │ economics.yaml      │
│   assumptions.yaml │ changeover_matrix.yaml │ disruption_scenarios.yaml │
└────────────────────────────┬─────────────────────────────────────────┘
                             │ loaded by
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      src/models/ (Dataclasses)                       │
│   Machine │ Operator │ Shift │ Order │ RoutingStep │ Customer        │
│   ChangeoverEntry │ ScheduleSlot │ Disruption │ CostBreakdown       │
└────────────────────────────┬─────────────────────────────────────────┘
                             │ used by
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
┌─────────────────┐ ┌───────────────┐ ┌──────────────────┐
│ src/data/        │ │ src/scheduler/ │ │ src/replanner/    │
│                  │ │               │ │                   │
│ generate.py      │ │ engine.py     │ │ disruption.py     │
│ load.py          │ │ strategies.py │ │ replan_engine.py  │
│ seed_data.py     │ │ heuristics.py │ │ explanation.py    │
└─────────────────┘ └───────┬───────┘ └────────┬──────────┘
                            │                   │
                            ▼                   ▼
                     ┌──────────────────────────────┐
                     │       src/validation/         │
                     │  feasibility.py               │
                     │  constraint_checker.py        │
                     └──────────────┬───────────────┘
                                    │
                                    ▼
                     ┌──────────────────────────────┐
                     │        src/costing/           │
                     │  calculator.py                │
                     │  comparison.py                │
                     └──────────────┬───────────────┘
                                    │
                     ┌──────────────┼──────────────┐
                     ▼              ▼              ▼
              ┌────────────┐ ┌────────────┐ ┌────────────────┐
              │ Dashboard  │ │ Reports    │ │ Defense/Demo   │
              │ (Web UI)   │ │ (Terminal) │ │ (Interactive)  │
              └────────────┘ └────────────┘ └────────────────┘
```

---

## 2. Module Descriptions

### 2.1 `config/` — Configuration Files

All configurable business assumptions live here. No magic numbers in code.

| File | Purpose |
|------|---------|
| `machines.yaml` | 14 machines (lathes, VMCs, HMC, **one** grinder, drills, conv. mill, CMM) — type, hourly rate, capabilities, MTBF/MTTR, planned maintenance windows |
| `operators.yaml` | Operators: name, qualifications, shift, skill level, wage |
| `shifts.yaml` | Shift definitions: times, productive hours, premiums |
| `economics.yaml` | Cost rates, overtime multipliers, penalty rates, caps |
| `assumptions.yaml` | All soft assumptions flagged for human review |
| `changeover_matrix.yaml` | Setup time/cost by machine type × material × operation transition |
| `disruption_scenarios.yaml` | Pre-defined disruption scenarios for demo/defense |

### 2.2 `src/models/` — Domain Model

Pure Python dataclasses with no business logic. Immutable where possible.

| File | Classes |
|------|---------|
| `machine.py` | `Machine`, `MachineType`, `MachineStatus` |
| `operator.py` | `Operator`, `SkillLevel` |
| `shift.py` | `Shift`, `ShiftType` |
| `order.py` | `Order`, `RoutingStep`, `OrderStatus`, `MaterialType`, `Operation` |
| `customer.py` | `Customer`, `CustomerTier` |
| `schedule.py` | `ScheduleSlot`, `SlotStatus`, `Schedule` |
| `changeover.py` | `ChangeoverEntry`, `ChangeoverCategory` |
| `disruption.py` | `Disruption`, `DisruptionType` |
| `cost.py` | `CostBreakdown`, `ScheduleCostSummary` |

### 2.3 `src/data/` — Data Generation & Loading

| File | Purpose |
|------|---------|
| `generate.py` | Master data generator (deterministic, seed=42) |
| `load.py` | Load generated data from JSON files |
| `seed_data.py` | Constants and seed values for generation |
| `customers.py` | Customer and order generation |
| `routings.py` | Realistic routing generation for parts |

### 2.4 `src/scheduler/` — Core Scheduling Engine

| File | Purpose |
|------|---------|
| `engine.py` | Main scheduler: takes data → produces Schedule |
| `strategies.py` | Three strategy implementations (cheapest, on-time, robust) |
| `heuristics.py` | Dispatching rules: EDD, SPT, weighted priority |
| `slot_allocator.py` | Assigns operations to machine-shift slots |
| `changeover_optimizer.py` | Groups jobs to minimize changeover |

#### Scheduling Algorithm (Proposed)

**Approach**: Priority-based dispatching heuristic with strategy-specific scoring.

```
1. INITIALIZE empty schedule grid (14 machines × 42 shifts)
2. SORT orders by strategy-specific priority:
   - Cheapest:  cost_efficiency_score (lower machine cost preference)
   - On-Time:   urgency_score (EDD + tier weight + slack)
   - Robust:    buffer_score (prefer machines with low breakdown rate)
3. FOR each order in priority order:
   a. FOR each routing step in sequence:
      i.   FIND eligible machines (by capability)
      ii.  FIND available slots (considering operator availability)
      iii. SCORE each (machine, slot) pair by strategy objective
      iv.  PICK best (machine, slot) considering changeover from prior job
      v.   ALLOCATE slot, update machine/operator availability
      vi.  VALIDATE feasibility constraints (HC-1 through HC-11)
4. POST-PROCESS: Calculate costs, identify late orders, compute penalties
5. VALIDATE: Run full feasibility check
6. OUTPUT: Schedule + CostSummary + Feasibility report
```

**Why heuristic over MIP/CP**: 
- Explainable: every decision traces to a scoring rule
- Fast: can replan in seconds for disruption scenarios  
- Tunable: strategy weights are in config
- Demonstrable: can walk through decisions in defense/demo

### 2.5 `src/replanner/` — Disruption Handling

| File | Purpose |
|------|---------|
| `disruption.py` | Disruption event handling and classification: MACHINE_BREAKDOWN, OPERATOR_ABSENCE, MATERIAL_DELAY, REWORK_REQUIRED, POWER_CUT (planned maintenance is handled as scheduled machine downtime, not a reactive disruption) |
| `replan_engine.py` | Replanning algorithm (freeze completed, reschedule remaining) |
| `explanation.py` | Generate human-readable explanation of changes |
| `impact.py` | Calculate cost impact of disruption |

#### Replanning Algorithm

```
1. RECEIVE disruption event (type, affected entity, duration)
2. FREEZE all completed and in-progress operations (HC-9)
3. IDENTIFY affected future slots:
   - Machine breakdown → all future slots on that machine
   - Operator absence → all future slots needing that operator
   - Material delay → all future slots for that order
   - Rework → insert rework steps, cascade downstream
4. REMOVE affected slots from schedule
5. RE-SCHEDULE affected operations using same strategy
   - Prefer alternative machines of same type
   - Prefer operators with available overtime capacity
   - Accept overtime/night shift if needed for high-priority orders
6. CALCULATE cost delta (before vs. after disruption)
7. GENERATE explanation: what changed, why, cost impact
8. VALIDATE new schedule feasibility
```

### 2.6 `src/validation/` — Feasibility Checking

| File | Purpose |
|------|---------|
| `feasibility.py` | Master validation: runs all checks, returns pass/fail + details |
| `constraint_checker.py` | Individual constraint checkers (HC-1 through HC-11) |

Every schedule output must pass:
- No machine double-booking
- All routing precedence respected
- All operators qualified and not double-assigned
- All changeover times accounted for
- No scheduling on broken-down machines
- Completed work not modified

### 2.7 `src/costing/` — Cost Calculation

| File | Purpose |
|------|---------|
| `calculator.py` | Per-slot and total cost calculation |
| `comparison.py` | Side-by-side comparison of three strategies |
| `traceable.py` | Generates traceable cost breakdown per slot |

> **Design note** (from assignment brief): the reader is *"a 50-year-old supervisor, not an
> engineer, possibly more comfortable in Kannada or Tamil than English."* The 6 AM view favors
> color-coded status, icons, and short labels over dense text/tables; any English copy stays
> short enough to be swapped for Kannada/Tamil strings later without a redesign. Full i18n is
> out of scope for this assessment (DERIVED DECISION — time-boxed), but the layout must not
> depend on paragraphs of English to be usable.

### 2.8 `src/dashboard/` — Supervisor 6 AM View

| File | Purpose |
|------|---------|
| `app.py` | Web server (Flask/FastAPI) |
| `views.py` | Dashboard view logic |
| `templates/` | HTML templates |
| `static/` | CSS, JS |

#### 6 AM Dashboard Contents

1. **Today's Production Plan**: Machine-by-machine, shift-by-shift for next 24h
2. **Yesterday's Performance**: Actual vs. planned completion
3. **At-Risk Orders**: Orders likely to miss due dates (flagged by tier)
4. **Machine Status**: Current status of all 14 machines
5. **Operator Attendance**: Expected vs. present operators
6. **Pending Disruptions**: Active issues requiring attention
7. **Cost Summary**: Running cost vs. budget for the 2-week horizon

### 2.9 `src/defense/` — Live Demo System

| File | Purpose |
|------|---------|
| `demo.py` | Interactive disruption injection |
| `scenarios.py` | Pre-built disruption scenarios |
| `presenter.py` | Format output for live presentation |

---

## 3. Data Flow

```
[Config YAML] → [Data Generator] → [JSON Data Files]
                                           │
                                    [Data Loader]
                                           │
                              ┌────────────┼────────────┐
                              ▼            ▼            ▼
                         [Cheapest]   [On-Time]    [Robust]
                         Strategy     Strategy     Strategy
                              │            │            │
                              └────────────┼────────────┘
                                           │
                                    [Validation]
                                           │
                                    [Cost Calculator]
                                           │
                              ┌────────────┼────────────┐
                              ▼            ▼            ▼
                        [Dashboard]  [Comparison]  [Defense Demo]
                                     Report
```

---

## 4. Technology Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Language | Python 3.11+ | Rapid development, rich ecosystem |
| Data model | `dataclasses` + `enum` | Type-safe, IDE-friendly, no ORM overhead |
| Config | YAML (`PyYAML`) | Human-readable, widely understood |
| Data storage | JSON files | Simple, versionable, no DB setup |
| Decimal math | `decimal.Decimal` | Exact currency calculations |
| Date/time | `datetime` (stdlib) | No external dependency |
| Web dashboard | Flask + Jinja2 | Lightweight, simple for supervisor view |
| Testing | `pytest` + `pytest-cov` | Industry standard |
| CLI | `argparse` or `click` | Simple command-line interface |
| Visualization | `matplotlib` (optional) | Gantt charts, cost plots |

---

## 5. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Heuristic vs. MIP solver | **Heuristic** | Explainable, fast replanning, demonstrable in defense |
| In-memory vs. database | **In-memory** | 14 machines × 42 shifts fits in memory; no DB complexity |
| Monolith vs. microservices | **Monolith** | Assessment scope; clean module boundaries suffice |
| REST API vs. server-rendered | **Server-rendered** | Simpler for supervisor view; no SPA complexity |
| Seed-based generation | **seed=42** | Reproducible data for testing and grading |

---

## 6. File/Module Dependency Rules

1. `models/` depends on nothing (pure data)
2. `data/` depends on `models/` and `config/`
3. `scheduler/` depends on `models/` and reads `config/`
4. `validation/` depends on `models/` only
5. `costing/` depends on `models/` and reads `config/`
6. `replanner/` depends on `scheduler/`, `validation/`, `costing/`, `models/`
7. `dashboard/` depends on everything but is a leaf node (no one depends on it)
8. `defense/` depends on `replanner/` and `dashboard/`

No circular dependencies. Business logic never imports from `dashboard/`.
