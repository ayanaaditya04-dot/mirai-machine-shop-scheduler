# Mission 2 Data Dictionary

All CSV files are UTF-8, comma-delimited, and use ISO-8601 dates/timestamps. `SOURCE_FACT` means stated by the Mirai brief; `ASSUMPTION` is an invented configurable operating rule; `DERIVED_FIELD` is calculated or normalized from other data.

| CSV | Columns and meaning |
|---|---|
| `machines.csv` | `machine_id` unique machine key; `name` display name; `machine_type` taxonomy; `capabilities` pipe-separated operation capabilities; `hourly_rate_inr` operating rate (DERIVED_FIELD); `max_regular_shifts_per_day` regular availability; `mtbf_hours`, `mttr_hours` reliability assumptions; `status` current status. |
| `operators.csv` | `operator_id` unique person key; `name`; `normal_shift` MORNING/AFTERNOON roster; `skill_level`; `hourly_rate_inr`; `overtime_willing` overtime assumption. |
| `operator_skills.csv` | `operator_id` to `machine_type` qualification relationship; `skill_level` qualification level. Exactly three GRINDER rows is a SOURCE_FACT constraint. |
| `shifts.csv` | `shift_id`; `date`; `shift_type`; `start_time`, `end_time`; `available_hours`; `is_regular_capacity`; `premium_multiplier`. Two regular shifts/day is SOURCE_FACT; timings/productive hours and NIGHT treatment are ASSUMPTIONS. |
| `customers.csv` | `customer_id`; `name`; `tier`; `revenue_share`; `just_in_time`; `late_penalty_pct_per_day`; `relationship_years`. One Tier 1 JIT account weighted to 60% is SOURCE_FACT; rates are configured assumptions. |
| `orders.csv` | `order_id`; `customer_id`; part identity/family; `quantity` (SOURCE_FACT range); `release_date`, `due_date`; `material`; `priority` DERIVED_FIELD; `order_value_inr` DERIVED_FIELD; `status`. |
| `operations.csv` | `operation_id`; `order_id`; `sequence`; `operation_type`; `required_machine_type`; `processing_time_per_piece_min` ASSUMPTION; `setup_changeover_family`; `quality_check_required`. Base routings contain 3-6 sequential operations (SOURCE_FACT). Rework rows use fractional sequence values. |
| `changeovers.csv` | `from_family`, `to_family`; `category`; `changeover_time_min`; `test_piece_cost_inr`. Same-family ~20 minutes and very different families up to ~180 minutes are SOURCE_FACT-aligned assumptions. |
| `maintenance.csv` | `maintenance_id`; `machine_id`; `start_time`, `end_time`; `duration_hours`. One 4-8 hour window per machine is an ASSUMPTION. |
| `breakdowns.csv` | `breakdown_id`; `machine_id`; `start_time`; `duration_hours`; `cause`. Frequency and durations are ASSUMPTIONS for reliability modeling. |
| `materials.csv` | `material_id`; `order_id`; `material_type`; `available_date`. Staggered availability is an ASSUMPTION for material-delay scenarios. |
| `rework_events.csv` | `rework_id`; `order_id`; `original_operation_id`; `failed_quantity`; `rework_operation_id`. Inspection failure 2-5% of pieces is SOURCE FACT; whether a failed batch becomes rework and its routing are ASSUMPTIONS. |

The fixed planning start is `2026-09-01` and the random seed is `42` (DERIVED implementation decisions). No scheduler is included in Mission 2.