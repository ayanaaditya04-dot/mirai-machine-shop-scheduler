"""Cross-strategy resilience comparison for Phase 4 validation."""
from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path

from src.models import Disruption, DisruptionType
from src.replanner import reschedule
from src.scheduler.engine import STRATEGIES, generate_schedule
from src.validation.schedule_validator import validate_schedule

CURRENT = datetime.fromisoformat("2026-09-01T11:00:00")


def _scenarios() -> dict[str, tuple[list[Disruption], int | None]]:
    return {
        "GRINDER_BREAKDOWN": ([Disruption("RES_GRINDER_BREAKDOWN", DisruptionType.MACHINE_BREAKDOWN, CURRENT, "GRINDER_01", 8, "Grinder breakdown")], None),
        "GRINDER_OPERATOR_ABSENCE": ([Disruption("RES_GRINDER_ABSENCE", DisruptionType.OPERATOR_ABSENCE, CURRENT, "OP_001", 8, "Grinder operator absence")], None),
        "NON_GRINDER_BREAKDOWN": ([Disruption("RES_VMC_BREAKDOWN", DisruptionType.MACHINE_BREAKDOWN, CURRENT, "CNC_VMC_01", 8, "VMC breakdown")], None),
        "MATERIAL_DELAY": ([Disruption("RES_MATERIAL_DELAY", DisruptionType.MATERIAL_DELAY, CURRENT + timedelta(days=1), "ORD_008", 0, "Order material delayed")], None),
        "REWORK_BATCH": ([Disruption("RES_REWORK", DisruptionType.REWORK_REQUIRED, CURRENT, "ORD_008", 0, "Inspection rework required")], 40),
    }


def _overtime(schedule):
    return sum((slot.end_time - slot.start_time).total_seconds() / 3600 for slot in schedule.slots if slot.shift_id.endswith("_NIGHT"))


def run_resilience(data_dir: str | Path = "data", output_file: str | Path = "outputs/resilience_comparison.csv"):
    output = Path(output_file)
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for scenario, (disruptions, rework_quantity) in _scenarios().items():
        for strategy in STRATEGIES:
            baseline = generate_schedule(strategy, data_dir)
            replanned = reschedule(baseline, CURRENT, disruptions, data_dir, rework_quantity)
            errors = validate_schedule(replanned.schedule, data_dir)
            if errors:
                raise ValueError(f"{scenario}/{strategy} rejected: {'; '.join(errors)}")
            baseline_late = sum(bool(row["late"]) for row in baseline.order_summary)
            replanned_late = sum(bool(row["late"]) for row in replanned.schedule.order_summary)
            baseline_tardy = sum(float(row["late_days"]) for row in baseline.order_summary)
            replanned_tardy = sum(float(row["late_days"]) for row in replanned.schedule.order_summary)
            tier1_ids = {row["order_id"] for row in baseline.order_summary if row["tier"] == "TIER_1"}
            delivery_changes = {item["order_id"] for item in replanned.impact["delivery_changes"]}
            rows.append({"Scenario": scenario, "Strategy": strategy, "Baseline Cost (INR)": baseline.cost_summary["total_cost"], "Replanned Cost (INR)": replanned.schedule.cost_summary["total_cost"], "Incremental Cost (INR)": replanned.impact["incremental_disruption_cost"], "Additional OT (hours)": round(_overtime(replanned.schedule) - _overtime(baseline), 3), "Additional Tardiness (days)": round(replanned_tardy - baseline_tardy, 3), "New Late Orders": replanned_late - baseline_late, "Tier-1 Impact": ",".join(sorted(tier1_ids & delivery_changes)) or "None", "Operations Moved": replanned.impact["operations_moved"], "Wasted Changeover (INR)": replanned.impact["wasted_changeover_cost"], "Unscheduled Operations": len(replanned.schedule.unscheduled_operations)})
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return rows


if __name__ == "__main__":
    for row in run_resilience():
        print(row)