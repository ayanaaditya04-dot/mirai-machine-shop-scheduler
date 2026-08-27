# Domain Model — Sridhar Precision Works

## 1. Entities

### 1.1 Machine

A physical machine on the shop floor capable of performing specific manufacturing operations.

```
Machine
├── machine_id: str              # e.g., "CNC_LATHE_01"
├── name: str                    # e.g., "CNC Lathe #1"
├── machine_type: MachineType    # enum: CNC_LATHE, CNC_VMC, CNC_HMC, SURFACE_GRINDER,
│                                #   CYLINDRICAL_GRINDER, WIRE_EDM, CONVENTIONAL_LATHE,
│                                #   RADIAL_DRILL, HORIZONTAL_BORING, MILLING_CONVENTIONAL,
│                                #   GEAR_HOBBING, BROACHING, HONING, CMM_INSPECTION
├── hourly_rate_inr: Decimal     # Operating cost per hour (INR)
├── capabilities: set[Operation] # Operations this machine can perform
├── max_shifts_per_day: int      # Typically 3
├── mtbf_hours: float            # Mean Time Between Failures
├── mttr_hours: float            # Mean Time To Repair
└── status: MachineStatus        # AVAILABLE, IN_USE, UNDER_MAINTENANCE, BROKEN_DOWN
```

### 1.2 Operator

A person who operates machines. Operators are qualified for specific machine types.

```
Operator
├── operator_id: str                    # e.g., "OP_001"
├── name: str                          
├── qualified_machines: set[MachineType] # Machine types they can operate
├── shift_assignment: ShiftType         # Which shift they normally work
├── overtime_willing: bool              # Whether they accept overtime
├── skill_level: SkillLevel             # JUNIOR, SENIOR, MASTER
└── hourly_rate_inr: Decimal            # Base wage per hour
```

> **SOURCE FACT** (assignment brief): *"only 3 people can run the grinding machine."*
> Data generation MUST pin `qualified_machines` for `GRINDER_01` to exactly 3 operators —
> this is a hard generation constraint, not a random outcome of qualification sampling.

### 1.3 Shift

A time block during which production can occur.

```
Shift
├── shift_type: ShiftType    # MORNING (6:00-14:00), AFTERNOON (14:00-22:00) — regular;
│                            #   NIGHT (22:00-06:00) — overtime-only, not baseline capacity
├── date: date               # Calendar date
├── start_time: datetime     
├── end_time: datetime       
├── available_hours: float   # Productive hours (after breaks) — 7.5h regular, 7.0h night
├── is_regular_capacity: bool # False for NIGHT — excluded from base 392-slot grid
└── premium_multiplier: float # 1.0 morning/afternoon; overtime multiplier applies for night
```

### 1.4 Order (Job)

A customer order requiring one or more manufacturing operations.

```
Order
├── order_id: str                 # e.g., "ORD_001"
├── customer: Customer            
├── part_name: str                # e.g., "Spindle Shaft"
├── part_number: str              
├── quantity: int                 # Number of parts to produce
├── due_date: datetime            
├── priority: int                 # Derived from customer tier + due date urgency
├── routing: list[RoutingStep]    # Ordered sequence of operations
├── material: MaterialType        # Affects changeover times
├── status: OrderStatus           # PENDING, IN_PROGRESS, COMPLETED, DELAYED
└── order_value_inr: Decimal      # Total order value (for penalty calculations)
```

### 1.5 RoutingStep

A single manufacturing operation within an order's routing.

```
RoutingStep
├── step_number: int              # Sequence position (1, 2, 3...)
├── operation: Operation          # e.g., TURNING, MILLING, GRINDING
├── required_machine_type: MachineType
├── estimated_time_per_piece_min: float  # Minutes per piece
├── setup_time_min: float         # Base setup/changeover time
├── can_run_parallel: bool        # Whether pieces can be batched
├── batch_size: int               # If parallel, how many per batch
└── quality_check_required: bool  # Whether inspection needed after this step
```

### 1.6 Customer

```
Customer
├── customer_id: str
├── name: str
├── tier: CustomerTier            # TIER_1 (strategic), TIER_2 (regular), TIER_3 (spot)
├── late_penalty_pct: float       # Penalty as % of order value per day late
├── just_in_time: bool            # JIT delivery commitment (drives urgency scoring)
└── relationship_years: int       # For context/display
```

> **SOURCE FACT** (assignment brief): *"One tier-1 customer is 60% of revenue, runs
> just-in-time, and penalises late delivery."* Data generation MUST designate exactly one
> customer as dominant: `tier=TIER_1`, `just_in_time=True`, and order-value allocation across
> the generated order book weighted so that customer accounts for ~60% of total order value.
> Remaining customers split the other ~40%, skewed toward smaller TIER_2/TIER_3 accounts per
> the brief's *"smaller customers pay better margins but tolerate delays."*

### 1.7 ChangeoverMatrix

Defines setup time when switching between different jobs on a machine.

```
ChangeoverEntry
├── machine_type: MachineType
├── from_material: MaterialType
├── to_material: MaterialType
├── from_operation: Operation
├── to_operation: Operation
├── changeover_time_min: float    # Additional setup time
└── changeover_cost_inr: Decimal  # Cost of wasted material/tooling
```

### 1.8 ScheduleSlot (Output)

A single scheduled operation on a specific machine during a specific shift.

```
ScheduleSlot
├── slot_id: str
├── machine_id: str
├── shift: Shift
├── order_id: str
├── routing_step: int
├── start_time: datetime
├── end_time: datetime
├── quantity_planned: int
├── setup_time_min: float          # Actual setup including changeover
├── operator_id: str
├── status: SlotStatus             # PLANNED, IN_PROGRESS, COMPLETED, CANCELLED, RESCHEDULED
└── cost_breakdown: CostBreakdown  # Detailed cost for this slot
```

### 1.9 Disruption

An event that forces replanning.

> **SOURCE FACT** (assignment brief) — the "reality attacks daily" list names five things:
> machine breakdowns, operator absenteeism, late raw material, planned maintenance windows,
> and **power cuts** ("run the diesel generator at 3× electricity cost, or lose the shift?").
> The earlier draft only modeled four `DisruptionType` values and dropped power cuts entirely.
> `POWER_CUT` is added below; planned maintenance is modeled as a scheduled machine-availability
> attribute (§1.1 Machine, `planned_maintenance_windows`) rather than a reactive disruption,
> since it's known in advance and doesn't need replanning to *discover* — only to route around.

```
Disruption
├── disruption_id: str
├── type: DisruptionType          # MACHINE_BREAKDOWN, OPERATOR_ABSENCE,
│                                 #   MATERIAL_DELAY, REWORK_REQUIRED, POWER_CUT
├── timestamp: datetime           # When the disruption occurs
├── affected_entity_id: str       # Machine ID, Operator ID, or Order ID (POWER_CUT: shop-wide, "SHOP")
├── duration_hours: float         # Expected duration of disruption
├── generator_available: bool     # POWER_CUT only — whether diesel generator can be run
├── generator_cost_multiplier: float # POWER_CUT only — 3.0× electricity portion of machine rate (ECONOMICS.md)
├── description: str              # Human-readable description
└── resolution: str               # How the replanner resolved it — for POWER_CUT: "ran generator" vs "lost shift"
```

`Machine` (§1.1) gains one more field to support planned maintenance:
```
Machine.planned_maintenance_windows: list[tuple[datetime, datetime]]  # known in advance, blocks scheduling like HC-10
```

### 1.10 CostBreakdown

```
CostBreakdown
├── machine_cost_inr: Decimal     # Machine hourly rate × duration
├── operator_cost_inr: Decimal    # Operator wage × duration
├── overtime_cost_inr: Decimal    # Premium above base rate
├── changeover_cost_inr: Decimal  # Wasted changeover cost
├── penalty_cost_inr: Decimal     # Late delivery penalty
├── total_cost_inr: Decimal       # Sum of above
└── notes: str                    # Explanation of any unusual costs
```

---

## 2. Enumerations

### MachineType

> **SOURCE FACT** (assignment brief): *"14 machines (CNC lathes, milling machines, drills, and
> one grinding machine that every job seems to need)."* The roster below is trimmed to exactly
> those families — 14 machines total, **one** grinder combining surface + cylindrical capability
> as the shop's deliberate bottleneck. Wire EDM, Horizontal Boring, Gear Hobbing, Broaching, and
> Honing from the earlier draft are dropped (DERIVED DECISION: not mentioned in the brief, and
> they roughly tripled the changeover-matrix surface area for no grading benefit). CMM is kept
> because the brief's own routing example ends "→ inspection."

| ID | Name | Typical Operations |
|----|------|--------------------|
| `CNC_LATHE_01` | CNC Lathe (Small, 2-axis) | Turning, Facing, Threading |
| `CNC_LATHE_02` | CNC Turn-Mill Center (Live Tooling) | Turning, Facing, Threading, Boring, Milling, Drilling |
| `CNC_VMC_01` | CNC Vertical Machining Center #1 | Milling, Drilling, Tapping, Reaming |
| `CNC_VMC_02` | CNC Vertical Machining Center #2 | Milling, Drilling, Tapping, Reaming |
| `CNC_VMC_03` | CNC Vertical Machining Center #3 | Milling, Drilling, Tapping, Reaming |
| `CNC_HMC_01` | CNC Horizontal Machining Center | Milling, Boring, Drilling, Tapping |
| `GRINDER_01` | **The Grinder** (surface + cylindrical) | Surface Grinding, Cylindrical Grinding — **the shop-wide bottleneck; only 3 operators qualified (SOURCE FACT)** |
| `CONV_LATHE_01` | Conventional Lathe #1 | Turning, Facing (manual) |
| `CONV_LATHE_02` | Conventional Lathe #2 | Turning, Facing (manual) |
| `RADIAL_DRILL_01` | Radial Drill #1 | Drilling, Tapping, Reaming |
| `RADIAL_DRILL_02` | Radial Drill #2 | Drilling, Tapping, Reaming |
| `MILLING_CONV_01` | Conventional Milling Machine #1 | Milling (manual) |
| `MILLING_CONV_02` | Conventional Milling Machine #2 | Milling (manual) |
| `CMM_01` | Coordinate Measuring Machine | Inspection, Quality Check |

### Operation
`TURNING`, `FACING`, `THREADING`, `BORING`, `MILLING`, `DRILLING`, `TAPPING`, `REAMING`,
`SURFACE_GRINDING`, `CYLINDRICAL_GRINDING`, `INSPECTION`

### MaterialType
`MILD_STEEL`, `EN8`, `EN24`, `EN31`, `STAINLESS_STEEL_304`, `STAINLESS_STEEL_316`,
`CAST_IRON`, `ALUMINIUM_6061`, `BRASS`, `BRONZE`

### CustomerTier
| Tier | Description | Late Penalty | Priority Weight |
|------|-------------|--------------|-----------------|
| `TIER_1` | Strategic / OEM customer | 2% of order value/day | 3× |
| `TIER_2` | Regular repeat customer | 1% of order value/day | 2× |
| `TIER_3` | Spot / one-time order | 0.5% of order value/day | 1× |

### ShiftType

> **SOURCE FACT** (assignment brief): *"2 shifts a day."* The brief separately says
> *"Sunday or third-shift running costs 1.5–2× labour"* — that describes an **overtime escape
> valve**, not a third regular roster shift. This corrects the earlier 3-regular-shift draft.

| Shift | Hours | Productive Hours | Type | Cost |
|-------|-------|-------------------|------|------|
| `MORNING` | 06:00–14:00 | 7.5h | Regular | 1.0× base rate |
| `AFTERNOON` | 14:00–22:00 | 7.5h | Regular | 1.0× base rate |
| `NIGHT` | 22:00–06:00 | 7.0h | **Overtime-only** — not baseline roster capacity | 1.5× first 4h, 2.0× beyond (§ECONOMICS.md) |

**Capacity model**: regular capacity = 14 machines × 14 days × 2 shifts = **392 machine-shift
slots** (corrects the earlier 588-slot figure, which assumed 3 regular shifts). NIGHT slots are
an overload valve the scheduler reaches for only when a regular shift can't fit the work, staffed
only by operators with `overtime_willing = True` — there is no fixed NIGHT roster assignment.

---

## 3. Hard Constraints (Non-Negotiable)

These are physical or logical constraints that **cannot** be violated in any valid schedule.

| # | Constraint | Rationale |
|---|-----------|-----------|
| HC-1 | A machine can process at most one operation at a time | Physical reality |
| HC-2 | Routing steps for an order must be executed in sequence | Manufacturing process dependency |
| HC-3 | An operator can operate at most one machine at a time | Physical reality |
| HC-4 | Each machine requires a qualified operator during operation | Safety and quality requirement |
| HC-5 | Setup/changeover must complete before production begins | Physical requirement |
| HC-6 | An operation cannot start before the previous routing step completes | Precedence constraint |
| HC-7 | Machine capacity cannot exceed available shift hours | Time is finite |
| HC-8 | CMM inspection cannot run simultaneously with parts being inspected | Logical dependency |
| HC-9 | Completed/in-progress operations cannot be modified during replanning | Historical integrity |
| HC-10 | A machine under breakdown cannot be scheduled until repaired | Physical reality |
| HC-11 | Night shift has reduced productive hours (7.0h vs 7.5h) | Longer breaks, handover |

---

## 4. Soft Constraints (Optimization Objectives)

These are preferences that the scheduler tries to satisfy but may violate under pressure.

| # | Constraint | Strategy Weighting |
|---|-----------|-------------------|
| SC-1 | Minimize total production cost | Cheapest (primary) |
| SC-2 | Meet all due dates | On-Time (primary) |
| SC-3 | Minimize machine utilization to leave slack for breakdowns | Robust (primary) |
| SC-4 | Minimize changeover time (group similar jobs) | All strategies |
| SC-5 | Balance load across machines of same type | All strategies |
| SC-6 | Prefer day shifts over night shifts (cost) | Cheapest |
| SC-7 | Prefer higher-skilled operators for critical operations | On-Time, Robust |
| SC-8 | Higher-tier customers get priority in contention | All strategies |
| SC-9 | Minimize overtime hours | Cheapest |
| SC-10 | Maintain buffer time before due dates | Robust (primary) |

---

## 5. Relationships Diagram

```
Customer (1) ──has──> (N) Order
Order (1) ──has──> (N) RoutingStep
RoutingStep (1) ──requires──> (1) MachineType
MachineType (1) ──implemented_by──> (N) Machine
Machine (1) ──has──> (N) ScheduleSlot
ScheduleSlot (1) ──assigned_to──> (1) Operator
ScheduleSlot (1) ──during──> (1) Shift
ScheduleSlot (1) ──for──> (1) Order × RoutingStep
ChangeoverMatrix ──between──> (MachineType, Material, Operation)
Disruption ──affects──> Machine | Operator | Order
```

---

## 6. Schedule Horizon

- **Planning horizon:** 14 calendar days (2 weeks)
- **Granularity:** Shift-level (2 regular shifts per day = 28 regular shift-slots per machine)
- **Total regular machine-shift slots:** 14 machines × 28 shifts = **392 schedulable slots**
- **NIGHT overtime pool:** up to 14 machines × 14 nights = 196 additional slots, usable only as
  overtime and only by `overtime_willing` operators — not counted in base capacity
- **Start date:** Configurable (default: next Monday from generation time)

---

## 7. Identified Ambiguities — APPROVED Defaults

> Status: approved to proceed as-is (2026-08-25). None of these contradict the assignment
> brief, so none block implementation. Each remains an ASSUMPTION, not a source fact — flagged
> here for the live defense session in case it's challenged.

| # | Ambiguity | Options | Default Assumption |
|---|-----------|---------|-------------------|
| A-1 | Can an order be split across machines of the same type? | Yes (split lots) / No (single machine per step) | **Yes**, with minimum batch size |
| A-2 | Can operations span across shifts? | Yes (carry over) / No (must complete in one shift) | **Yes**, operations can span shifts |
| A-3 | Is there a maximum overtime limit per operator per week? | Indian law limits to 50 hrs/quarter | **12 hours/week max overtime** |
| A-4 | Do all 14 machines run both regular shifts, and can any reach NIGHT overtime? | Yes / Only some run night shift | **All machines run both regular shifts**; any machine can be pushed into NIGHT overtime, but only with an `overtime_willing` qualified operator |
| A-5 | How is rework handled? | Re-enter routing from failed step / New order | **Re-enter routing from failed step**, same order ID |
| A-6 | Material delay: does it block the entire order or just the first step? | Entire order / Just first step | **Just the first step** (subsequent steps may already have WIP) |
| A-7 | Is the CMM a bottleneck (shared inspection resource)? | Yes / No | **Yes** — all quality-critical steps route through CMM |
| A-8 | Are weekends included in the 14-day horizon? | Yes (some shops run weekends) / No | **Yes**, with weekend premium (1.5×) |
| A-9 | What is the minimum batch size for lot splitting? | Need to define | **10 pieces** or 25% of order quantity, whichever is smaller |
| A-10 | Does the "6 AM view" mean a static report or live dashboard? | Static PDF / Interactive web | **Interactive web dashboard** (for demo capability) |
| A-11 | Power cut: is the generator decision automatic or does it require supervisor approval? | Auto-run generator / Flag for decision | **Flag for decision** — replanner presents "run generator (₹X) vs. lose shift (₹Y in penalties/delay)" as an explicit choice, since this is the owner's kind of call, not the algorithm's |
| A-12 | How often are planned maintenance windows scheduled? | Need to define | **1 window per machine per 14-day horizon, 4–8 hours**, randomly placed but deterministic (seed=42) |
