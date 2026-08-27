# Economics Model — Sridhar Precision Works

All monetary values are in Indian Rupees (₹ / INR). All rates are configurable via `config/economics.yaml`.

---

## 1. Machine Operating Costs

Machine hourly rates include: depreciation, electricity (₹8.50–₹10.50/kWh commercial), cutting consumables, coolant, and floor-space overhead.

| Machine ID | Machine Name | Hourly Rate (₹) | Notes |
|------------|-------------|-----------------|-------|
| `CNC_LATHE_01` | CNC Turning Center (Small, 2-axis) | ₹550 | Standard 2-axis production lathe |
| `CNC_LATHE_02` | CNC Turn-Mill Center (Live Tooling) | ₹1,100 | Live tools + C/Y-axis; higher consumable cost |
| `CNC_VMC_01` | 3-Axis CNC VMC #1 | ₹800 | Standard production VMC |
| `CNC_VMC_02` | 3-Axis CNC VMC #2 | ₹800 | Identical to VMC #1 |
| `CNC_VMC_03` | 3-Axis CNC VMC #3 | ₹800 | Identical to VMC #1/#2 |
| `CNC_HMC_01` | Twin-Pallet CNC HMC | ₹1,800 | High-value machine; pallet system |
| `GRINDER_01` | CNC Grinder (surface + cylindrical) | ₹750 | **The shop's one grinder — bottleneck resource; wheel dressing costs** |
| `CONV_LATHE_01` | Heavy-Duty Conventional Lathe #1 | ₹300 | Low overhead; manual operation |
| `CONV_LATHE_02` | Heavy-Duty Conventional Lathe #2 | ₹300 | Identical to CONV_LATHE_01 |
| `RADIAL_DRILL_01` | Heavy Radial Drilling Machine #1 | ₹250 | Lowest cost machine |
| `RADIAL_DRILL_02` | Heavy Radial Drilling Machine #2 | ₹250 | Identical to RADIAL_DRILL_01 |
| `MILLING_CONV_01` | Universal Turret Milling Machine #1 | ₹280 | Manual milling; rework and prototypes |
| `MILLING_CONV_02` | Universal Turret Milling Machine #2 | ₹280 | Identical to MILLING_CONV_01 |
| `CMM_01` | Coordinate Measuring Machine | ₹400 | No cutting; air-conditioned room overhead |

> Roster trimmed from an earlier draft that included Wire EDM, Horizontal Boring, and a second
> grinder — none appear in the assignment brief, which names only "CNC lathes, milling machines,
> drills, and one grinding machine." (DERIVED DECISION, see DOMAIN_MODEL.md §MachineType.)

---

## 2. Operator Costs

### Base Wage Rates (per 8-hour shift)

| Skill Level | Monthly Salary (₹) | Per-Shift Cost (₹) | Hourly Rate (₹) |
|-------------|--------------------|--------------------|-----------------|
| **MASTER** (Setter-Programmer) | ₹45,000 | ₹1,730 | ₹215 |
| **SENIOR** (Skilled CNC Operator, ITI 3-5 yrs) | ₹26,000 | ₹1,000 | ₹125 |
| **JUNIOR** (Semi-skilled, ≤2 yrs) | ₹18,000 | ₹690 | ₹85 |

> **Calculation**: Monthly ÷ 26 working days = per-shift. Per-shift ÷ 8 = hourly.

### Overtime & Premium Rates

| Condition | Multiplier | Legal Basis |
|-----------|-----------|-------------|
| Regular hours (≤9h/day, ≤48h/week) | 1.0× | Factories Act, 1948 |
| Overtime (statutory) | **2.0×** | Section 59, Factories Act |
| Night shift premium | +₹100/shift flat | Industry practice |
| Weekend / holiday work | **2.0×** | Standard practice |

> **Assumption (configurable)**: For this model, we use **1.5× for the first 4h overtime**, **2.0× beyond 4h**, per common MSME practice. This is flagged as an assumption in `config/assumptions.yaml`.

### Overtime Limits

| Constraint | Value | Source |
|-----------|-------|--------|
| Max overtime per day | 4 hours | Practical limit |
| Max overtime per week | 12 hours | Configurable assumption |
| Max overtime per quarter | 50 hours | Factories Act, 1948 |

---

## 3. Changeover Costs

Changeover cost = Machine idle time cost + Operator idle time cost + Scrap/test piece cost.

$$\text{Changeover Cost} = t_{setup} \times (R_{machine} + R_{operator}) + C_{test\_piece}$$

### Changeover Time Categories

| Category | Conditions | Time Range (min) | Typical Test Piece Cost (₹) |
|----------|-----------|-----------------|---------------------------|
| **MINOR** | Same material family, same fixture, different part | 15–30 | ₹0 |
| **MEDIUM** | Different part, same material, fixture swap | 35–60 | ₹150 |
| **MAJOR** | Different material + new fixture + dedicated tooling | 75–150 | ₹300 |

### Example Calculation

> Major changeover on CNC_VMC_01 (₹800/hr) with SENIOR operator (₹125/hr):
> - Setup time: 90 min = 1.5 hours
> - Machine cost: 1.5 × ₹800 = ₹1,200
> - Operator cost: 1.5 × ₹125 = ₹187.50
> - Test piece: ₹300
> - **Total: ₹1,687.50**

---

## 3B. Power Cut / Diesel Generator Cost

> **SOURCE FACT** (assignment brief): *"power cuts (run the diesel generator at 3× electricity
> cost, or lose the shift?)."* Missing from the earlier draft entirely — added here.

Machine hourly rates (§1) are a blend of depreciation, electricity, consumables, and overhead.
For generator-run cost purposes we treat **40% of a machine's hourly rate as its electricity
component** (ASSUMPTION — not stated in the brief, needs confirmation) and apply the 3× penalty
to that component only; depreciation/consumables/overhead don't change just because power comes
from a generator.

$$R_{generator} = R_{machine} \times \big(0.6 + 0.4 \times 3\big) = R_{machine} \times 1.8$$

**Decision at each power cut** (see DOMAIN_MODEL.md A-11 — flagged for supervisor/owner, not
automatic):
- **Run generator**: pay `R_generator` (1.8× normal machine rate) for every affected machine for
  the outage duration, operators paid normally, no lost production.
- **Lose the shift**: zero machine/operator cost for the outage window, but every operation that
  would have run in that window is delayed — risking late-penalty exposure (§4) if it pushes a
  tier-1/JIT order past due date.

The replanner must compute and present both totals side by side; this is one of the "what phone
call should the owner make right now" decisions called out for the live defense session.

## 4. Late Delivery Penalties

Penalties are charged as a percentage of order value per day late, varying by customer tier.

| Customer Tier | Penalty Rate | Maximum Cap | Escalation |
|---------------|-------------|-------------|------------|
| **TIER_1** (Strategic/OEM) | 2% of order value / day | 10% of order value | Assembly line stoppage liability |
| **TIER_2** (Regular B2B) | 1% of order value / day | 8% of order value | Replacement guarantee |
| **TIER_3** (Spot/Prototype) | 0.5% of order value / day | 5% of order value | Best-effort; minimal |

### Penalty Calculation

$$P_{late} = \min\left( d_{late} \times r_{penalty} \times V_{order},\ cap_{max} \times V_{order} \right)$$

Where:
- $d_{late}$ = number of days late
- $r_{penalty}$ = daily penalty rate (decimal)
- $V_{order}$ = total order value (₹)
- $cap_{max}$ = maximum penalty cap (decimal)

### Example

> Order value: ₹2,00,000. Customer: TIER_1. Days late: 3.
> - Penalty = min(3 × 0.02 × 2,00,000, 0.10 × 2,00,000)
> - Penalty = min(₹12,000, ₹20,000)
> - **Penalty: ₹12,000**

---

## 5. Total Schedule Cost Formula

The total cost of a schedule is the sum of all slot costs plus penalties:

$$C_{total} = \sum_{slots} \left( C_{machine} + C_{operator} + C_{overtime} + C_{changeover} \right) + \sum_{late\ orders} P_{late}$$

### Component Breakdown

| Component | Formula | Description |
|-----------|---------|-------------|
| Machine cost | $t_{operation} \times R_{machine}$ | Machine running time × hourly rate |
| Operator cost | $t_{operation} \times R_{operator}$ | Operator time × base hourly rate |
| Overtime cost | $t_{overtime} \times R_{operator} \times (m_{overtime} - 1)$ | Only the premium portion |
| Changeover cost | Per changeover calculation (§3) | Setup between different jobs |
| Late penalty | Per penalty calculation (§4) | Applied per order, not per operation |
| **Wasted changeover** | Full changeover cost when disruption invalidates a setup | Sunk cost from breakdowns |

---

## 6. Order Value Estimation

For generating realistic data, order values are estimated from:

$$V_{order} = Q \times \sum_{steps} \left( \frac{t_{step}}{60} \times (R_{machine} + R_{operator}) \right) \times (1 + m_{profit})$$

Where:
- $Q$ = order quantity
- $t_{step}$ = per-piece time in minutes for each routing step
- $R_{machine}$, $R_{operator}$ = respective hourly rates
- $m_{profit}$ = profit margin multiplier (varies by tier: TIER_1=15%, TIER_2=25%, TIER_3=45%)

---

## 7. Cost Traceability Requirements

Every cost line-item in the output must include:

```
{
  "slot_id": "SLOT_001",
  "order_id": "ORD_005",
  "routing_step": 2,
  "machine_id": "CNC_VMC_01",
  "operator_id": "OP_003",
  "duration_hours": 3.5,
  "machine_rate_per_hour": 800,
  "operator_rate_per_hour": 125,
  "overtime_hours": 0.0,
  "overtime_multiplier": 1.5,
  "changeover_time_hours": 0.75,
  "changeover_cost": 693.75,
  "machine_cost": 2800.00,
  "operator_cost": 437.50,
  "overtime_cost": 0.00,
  "total_slot_cost": 3931.25,
  "notes": "Medium changeover from EN8 to EN24 steel"
}
```

---

## 8. Strategy-Specific Cost Behavior

| Metric | Cheapest | Most On-Time | Most Robust |
|--------|----------|-------------|-------------|
| Overtime hours | Minimized | Accepted if needed for deadlines | Moderate |
| Night shift usage | Avoided (1.25× premium) | Used freely | Used as buffer |
| Changeover grouping | Aggressively grouped | Secondary concern | Moderately grouped |
| Penalty exposure | Accepts some late deliveries | Minimized | Moderate |
| Machine utilization | Moderate-high | High | Conservative (≤75%) |
| Buffer time | None | Minimal | Significant (≥1 shift) |
