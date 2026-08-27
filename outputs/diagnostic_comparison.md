# Strategy Diagnostic Comparison

Computed from the existing exported schedules. Utilization denominators are 210 regular hours per machine/operator across the 14-day horizon. Machine/operator occupied time includes setup. `Moved vs CHEAPEST` compares machine, operator, and shift assignment for the same operation.

| Metric | CHEAPEST | MOST_ON_TIME | MOST_ROBUST |
|---|---:|---:|---:|
| Total cost (INR) | 194190.15 | 224624.06 | 195843.28 |
| Machine cost (INR) | 133607.57 | 132534.67 | 136353.80 |
| Operator cost (INR) | 23441.70 | 29020.77 | 23923.79 |
| Overtime cost (INR) | 4254.30 | 1292.62 | 5213.52 |
| Changeover cost (INR) | 32886.58 | 61776.00 | 30352.17 |
| Total overtime hours | 59.753 | 24.873 | 72.362 |
| Late orders | 0 | 0 | 0 |
| Total late days | 0.000 | 0.000 | 0.000 |
| On-time orders | 25 | 25 | 25 |
| Average lateness (days) | 0.000 | 0.000 | 0.000 |
| Maximum lateness (days) | 0.000 | 0.000 | 0.000 |
| Average machine utilization | 9.32% | 10.34% | 9.19% |
| Maximum machine utilization | 28.63% | 36.94% | 28.27% |
| Grinder utilization | 16.91% | 16.91% | 16.91% |
| Operator utilization | 26.09% | 20.67% | 16.09% |
| Unscheduled operations | 0 | 0 | 0 |
| Total schedule makespan (hours) | 149.543 | 231.229 | 139.335 |
| Average slack before due date (days) | 9.445 | 7.335 | 9.622 |
| Operations moved vs CHEAPEST | 0 | 116 | 91 |

## Top 10 Differing Decisions

Assignments are shown as `machine / operator / shift` for the same operation.

| Operation | CHEAPEST | MOST_ON_TIME | MOST_ROBUST |
|---|---|---|---|
| OPR_025_04 | CMM_01 / OP_007 / SH_01_NIGHT | CMM_01 / OP_005 / SH_02_AFTERNOON | CMM_01 / OP_007 / SH_02_MORNING |
| OPR_025_03 | RADIAL_DRILL_01 / OP_002 / SH_01_NIGHT | RADIAL_DRILL_01 / OP_002 / SH_02_MORNING | RADIAL_DRILL_02 / OP_013 / SH_02_MORNING |
| OPR_025_02 | CNC_VMC_01 / OP_002 / SH_01_NIGHT | CNC_VMC_01 / OP_005 / SH_02_MORNING | CNC_VMC_02 / OP_010 / SH_01_NIGHT |
| OPR_025_01 | CNC_LATHE_01 / OP_002 / SH_01_NIGHT | CNC_LATHE_01 / OP_008 / SH_02_MORNING | CNC_LATHE_01 / OP_007 / SH_01_NIGHT |
| OPR_024_05 | GRINDER_01 / OP_001 / SH_04_AFTERNOON | GRINDER_01 / OP_001 / SH_10_AFTERNOON | GRINDER_01 / OP_001 / SH_04_MORNING |
| OPR_024_04 | RADIAL_DRILL_01 / OP_002 / SH_04_AFTERNOON | RADIAL_DRILL_01 / OP_002 / SH_10_AFTERNOON | RADIAL_DRILL_02 / OP_002 / SH_04_MORNING |
| OPR_024_03 | CNC_VMC_03 / OP_010 / SH_04_MORNING | CNC_VMC_01 / OP_005 / SH_10_AFTERNOON | CNC_VMC_02 / OP_010 / SH_04_MORNING |
| OPR_024_02 | CNC_LATHE_02 / OP_010 / SH_04_MORNING | CNC_LATHE_02 / OP_006 / SH_05_AFTERNOON | CNC_LATHE_02 / OP_010 / SH_03_NIGHT |
| OPR_023_03 | CNC_VMC_02 / OP_002 / SH_05_MORNING | CNC_VMC_01 / OP_003 / SH_10_MORNING | CNC_VMC_03 / OP_002 / SH_04_NIGHT |
| OPR_023_01 | CNC_VMC_03 / OP_010 / SH_04_NIGHT | CNC_VMC_01 / OP_005 / SH_09_AFTERNOON | CNC_VMC_02 / OP_002 / SH_04_NIGHT |

The current dataset produces no late orders, so lateness and penalty metrics are zero across all three strategies. `MOST_ON_TIME` uses fewer overtime hours but incurs substantially more changeover cost; `MOST_ROBUST` has the shortest makespan and lowest average operator utilization in these exports.
