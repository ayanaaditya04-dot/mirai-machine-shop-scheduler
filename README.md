# Mirai Machine Shop Scheduler

**A 2-week production scheduler for a 40-person auto-components machine shop — built to hand a real, non-technical shift supervisor three honestly-compared trade-off plans instead of one black-box answer.**

Live app: https://mirai-machine-shop-scheduler-lcpuzsxz9fyimfejxrh4sx.streamlit.app

---

## Why this exists

This started from a brief describing a real-sounding, messy shop floor problem, not a clean optimization textbook problem: Sridhar Precision Works has 14 machines but only **one** grinder, one huge JIT customer worth 60% of revenue, operators who aren't interchangeable (only 3 of them can even run the grinder), and five different ways a day can go sideways — a machine breaks, someone doesn't show up, material arrives late, maintenance eats a shift, or the power goes out and you're stuck paying 3x for diesel.

The brief was also explicit about something a lot of scheduling tools get wrong: **delivering a single schedule is called out as an automatic weakness.** The supervisor doesn't want "the answer" — they want to see cheapest, most-on-time, and most-robust laid out side by side, with a real recommendation and the reasoning behind it, in a format a 50-year-old non-engineer supervisor who's more comfortable in Tamil or Kannada than English can actually read at 6 AM.

That reframes what this project is really about. The algorithm matters, but the harder and more interesting problem was: **how do you turn a brief that gives real constraints but almost no absolute numbers into a dataset and a system you can actually defend?** That question shaped almost every design decision below.

---

## The three-way traceability rule

Every number in this project is labeled as one of three things, and that labeling is enforced as a discipline throughout the codebase and config files, not just in one summary doc:

- **SOURCE FACT** — stated directly in the assignment brief. Not up for debate; if it changed, I'd have misread the brief.
- **ASSUMPTION** — the brief gives no number, so I picked one and documented why. These are the numbers a reviewer should feel free to challenge.
- **DERIVED** — computed from other data (e.g., `order_value_inr = unit_price × quantity`). Not a judgment call, just arithmetic.

You'll see this pattern called out in code comments, in `config/assumptions.yaml`, and in `DATA_DICTIONARY.md`. The point isn't ceremony — it's that anyone auditing this project (a grader, an interviewer, a future engineer) can tell at a glance which numbers are load-bearing facts and which ones are my judgment calls, and can push back on the judgment calls specifically instead of distrusting the whole dataset.

---

## Repository structure, folder by folder

```
.
├── Skeleton/                  Design docs written BEFORE any code — the paper trail
├── config/                    Every business assumption, as YAML — no magic numbers in code
├── data/                      The generated, deterministic dataset (CSV)
├── src/                       All the logic: generation, validation, scheduling, replanning
├── tests/                     pytest suite — data integrity, scheduler behavior, replanning
├── outputs/                   Generated reports: schedules, cost summaries, trade-off memos
├── app.py                     The Streamlit dashboard — what the supervisor actually opens
├── requirements.txt           pandas, PyYAML, streamlit, pytest
└── DATA_DICTIONARY.md         Column-by-column documentation of every CSV
```

### `Skeleton/` — the design-first paper trail

Before writing any generation or scheduling code, four documents were written and approved:

- **`DOMAIN_MODEL.md`** — every entity in the system (Machine, Operator, Order, RoutingStep, etc.) as a structured spec, including the full machine taxonomy: `CNC_LATHE`, `CNC_VMC`, `CNC_HMC`, `GRINDER`, `CONV_LATHE`, `RADIAL_DRILL`, `MILLING_CONV`, `CMM_INSPECTION`. This is the taxonomy every other file in the repo has to agree with — no synonyms allowed (e.g. you will never see "lathe" in one file and "CNC_LATHE" in another).
- **`ECONOMICS.md`** — the full cost model: machine hourly rates (₹250–₹1,800 depending on machine class), what's baked into each rate (depreciation, electricity, consumables, floor overhead), and the overtime/diesel multipliers straight from the brief.
- **`ARCHITECTURE.md`** — the system design diagram this README's folder structure follows.
- **`PROJECT_PLAN.md`** — a phase-by-phase build plan (Phase 0 = foundation, through Phase 6 = defense/demo system), including an explicit **human-approval gate** before any code was written, and a **risk register** naming known trouble spots up front rather than discovering them later.

This folder exists because a scheduler you can't explain is a scheduler nobody on a shop floor should trust. Writing the domain model and economics down *before* code meant every later decision could be checked against something concrete instead of against memory.

### `config/` — every assumption, in one auditable place

| File | What it controls |
|---|---|
| `machines.yaml` | The 14-machine fleet: type, hourly rate, MTBF/MTTR reliability numbers |
| `operators.yaml` | Roster, qualifications, shift assignment, skill level |
| `shifts.yaml` | Shift clock times and productive-hour assumptions |
| `economics.yaml` | Wage rates, overtime multipliers, diesel-generator multiplier, penalty rates |
| `customers_orders.yaml` | Customer tiers and the ~25-order book |
| `changeover_matrix.yaml` | Setup time by part-family transition (20 min same-family → up to 3 hr cross-family) |
| `disruption_scenarios.yaml` | Pre-built scenarios for live demo/defense, including the exact scenario described in the brief itself (grinder down 8+ hours, Thursday JIT delivery, one grinder operator absent) |
| `assumptions.yaml` | The consolidated, human-readable register of every ASSUMPTION and why it was made |
| `scheduling.yaml` | The objective-function weights for each of the three strategies |

If you ever want to change a business rule — a wage rate, a penalty, a shift time — this is the only place you should need to touch. Nothing downstream hardcodes a number that belongs here.

### `data/` — the generated dataset

CSVs for machines, operators, operator skills, shifts, customers, orders, operations/routings, changeovers, maintenance, breakdowns, materials, and rework events, plus a `quality_report.json` summarizing feasibility. Every file here is produced deterministically (seed = 42) from `config/` — running the generator twice produces byte-identical output. `DATA_DICTIONARY.md` documents every single column: type, meaning, and whether it's SOURCE FACT, ASSUMPTION, or DERIVED.

**Why determinism matters here specifically:** if the supervisor asks "why did the plan change overnight," the only acceptable answer is "because something real changed" (a breakdown, a new order) — never "because the random seed landed differently." Determinism is what makes that guarantee possible.

### `src/` — the logic, layered so nothing depends on something above it

```
src/
├── models/            Pure data classes — Machine, Operator, Order, Shift, Cost, Disruption...
│                       (zero business logic — just structure and the shared enums, e.g.
│                        MachineType, Operation, MaterialType, SkillLevel, ShiftType)
├── data/               Data generation: customers.py, machines_gen.py, operators_gen.py,
│                       seed_data.py, load.py
├── data_generator.py   Orchestrates the full dataset build
├── data_validator.py   Hard data-integrity checks (see Testing below)
├── quality_report.py   Feasibility/realism analysis — bottlenecks, demand vs. capacity
├── scheduler/
│   └── engine.py       The core scheduling algorithm — see "How Scheduling Works" below
├── validation/
│   └── schedule_validator.py   Checks a PRODUCED schedule for feasibility (no double-booking,
│                                routing order respected, no scheduling on broken machines...)
├── replanner/
│   └── replan_engine.py   Disruption handling: freeze completed work, reschedule the rest
├── run_scheduler.py    CLI entry point — generates a schedule for a given strategy
├── replan_demo.py       CLI entry point — runs a disruption scenario end-to-end
├── resilience_report.py Compares how each strategy holds up under each disruption type
└── final_memo.py        Generates the trade-off memo and recommendation text
```

**Dependency rule, enforced throughout:** `models/` depends on nothing. `data/` depends on `models/` and `config/`. `scheduler/` depends on `models/` and reads `config/`. `replanner/` depends on `scheduler/`, `validation/`, and `models/`. Nothing in the business logic ever imports from the dashboard — the dashboard is a leaf node that depends on everything else, never the other way around. This isn't decorative — it's what makes it possible to test the scheduler completely independently of Streamlit ever running.

### `tests/` — the pytest suite

- `test_data/test_mission2.py` — dataset integrity: machine count, grinder count, exactly 3 grinder-qualified operators, foreign keys across every table, routing sequence validity, deterministic regeneration.
- `test_data/test_scheduler.py` — scheduler behavior: strategy differences are real, no constraint violations in produced schedules.
- `test_replanning.py` — disruption handling: completed work stays frozen, affected slots actually get rescheduled.
- `test_final_memo.py`, `test_app.py` — output generation and app-level sanity.

All 25 tests pass as of the last run.

### `outputs/` — what the system actually produces

For each of the three strategies (`cheapest`, `most_on_time`, `most_robust`) and each disruption scenario (breakdown, material delay, operator absence, rework, cascading), you'll find a generated schedule, a cost summary, an order summary, and — for disruptions — a human-readable plain-text explanation of exactly what changed and why (`replan_explanation_*.txt`). `final_tradeoff_memo.md` and `strategy_tradeoff_report.txt` are the synthesized "here's the recommendation and why" documents the supervisor-facing app is built on top of.

### `app.py` — the Streamlit dashboard

Six tabs: **6 AM Shift Briefing**, **Schedule**, **Orders**, **Disruptions**, **Cost & Trade-offs**, **Final Recommendation**. The briefing tab supports English, Tamil, and Kannada — not a nice-to-have, a direct response to the brief's persona: a 50-year-old non-engineer supervisor more comfortable in Kannada or Tamil than English. A sidebar toggle lets you switch which of the three planning strategies is active and see every tab update accordingly.

---

## How scheduling actually works

The engine is a **priority-based dispatching heuristic**, not a MIP/CP solver — chosen deliberately, and documented as a trade-off rather than a default:

- **Explainable** — every placement decision traces back to a scoring rule you can point at, which matters when a non-engineer supervisor asks "why did you pick this machine."
- **Fast** — replanning after a disruption needs to run in minutes per the brief, not run an overnight solve.
- **Tunable** — strategy weights live entirely in `config/scheduling.yaml`, not buried in code.

For each of the three strategies, every candidate (machine, shift, operator) for the next operation gets scored, and the lowest-scoring candidate is picked:

- **CHEAPEST** — weights machine cost, operator cost, changeover cost, and overtime cost heavily; lateness is a real but secondary cost term.
- **MOST_ON_TIME** — weights lateness cost and due-date urgency heavily, with tier priority breaking ties (tier-1/JIT orders get first claim on contested slots).
- **MOST_ROBUST** — weights machine reliability risk, grinder-specific bottleneck pressure, and operator scarcity, preferring options that leave slack for absorbing a future disruption rather than the tightest possible plan.

Disruption replanning follows a fixed sequence: freeze everything already completed or in progress, identify every future slot the disruption actually touches (a machine breakdown only affects that machine's future slots; a material delay only affects that order's future slots), remove and reschedule just those slots using the same strategy, then recompute the cost delta and generate a plain-language explanation of what changed.

---

## Running it locally

```bash
pip install -r requirements.txt
python3 src/data_generator.py      # regenerate the dataset (deterministic, seed=42)
python3 -m pytest tests/ -v        # run the full test suite
python3 src/run_scheduler.py       # produce a schedule for a chosen strategy
streamlit run app.py               # launch the dashboard locally
```

---

## What I'd flag if you're auditing this yourself

I'd rather name these than have someone find them first:

- **Customer tiers extend beyond the brief.** The brief describes exactly two tiers — one JIT tier-1 customer and "smaller customers" who tolerate delay. This project splits "smaller customers" into TIER_2 and TIER_3 to add pricing/margin granularity within that group. It's a documented extension, not a misreading, but it's fair to ask why, and worth knowing the answer before someone asks.
- **The dashboard's "at risk" label can look counter-intuitive at first glance.** The MOST_ON_TIME strategy can show *more* orders flagged "tight margin" than the other strategies while simultaneously having the *fewest orders actually late* — because it deliberately trims buffer across many orders rather than leaving generous slack on some and letting others slip. That's the strategy working as intended, not a bug, but the label doesn't make that distinction obvious on its own yet.
- **Generated timestamps carry full floating-point precision** in a couple of places (e.g., `10:28:41.820000`) because processing time is computed from `minutes_per_piece × quantity` as a float. It's deterministic, not a bug, but it's not what a 6 AM supervisor should have to read — rounding to the nearest minute is a pending polish item.

None of these are hidden — they're exactly the kind of thing worth being able to explain in one sentence if someone asks, rather than being caught off guard by your own project.

---

## A quick word on how this was built

This was built and verified iteratively, not written once and shipped. Two examples worth mentioning because they're representative of the whole process:

1. An early version of the dataset had the grinder needing roughly **7x** its available two-week capacity — obviously broken. The fix wasn't to fudge the numbers; it was to diagnose *why* (due dates were clustered too tightly for a 25-order backlog that's actually a rolling pipeline, not a one-shot batch), fix the generator's assumptions, and regenerate. It now sits at a genuinely tight-but-feasible ratio, which is the actual bottleneck the brief describes — not an artifact of bad data.
2. After deploying, the shift briefing was flagging **25 out of 25 orders as "at risk"** with zero disruptions applied — a dead giveaway something was wrong. It traced to a real logic bug (a filter comparing a value that's mathematically clamped to always be ≥ 0 against a threshold of −1, which made the condition always true). That got fixed and verified: 25 → 12. A second suspected bug — the MOST_ON_TIME strategy looking backwards — turned out, after actually testing a proposed fix against the real scheduler output, to **not** be a bug at all; the "fix" made real lateness measurably worse, so it was reverted rather than shipped. Every claim in this README about what does and doesn't work has been checked against actual output the same way, not asserted from reading the code alone.
