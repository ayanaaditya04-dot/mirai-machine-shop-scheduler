"""Dataset-level realism and feasibility report for Mission 2."""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from src.data_generator import PLANNING_START


def _rows(directory: Path, name: str):
    with (directory / f"{name}.csv").open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def build_report(data_dir: str | Path = "data") -> dict:
    directory = Path(data_dir)
    orders, operations = _rows(directory, "orders"), _rows(directory, "operations")
    machines, operators = _rows(directory, "machines"), _rows(directory, "operators")
    skills, shifts = _rows(directory, "operator_skills"), _rows(directory, "shifts")
    changeovers, maintenance = _rows(directory, "changeovers"), _rows(directory, "maintenance")
    breakdowns, reworks = _rows(directory, "breakdowns"), _rows(directory, "rework_events")
    quantities = [int(row["quantity"]) for row in orders]
    by_capability = Counter()
    workload_by_machine = defaultdict(float)
    machine_by_type = defaultdict(list)
    for machine in machines:
        machine_by_type[machine["machine_type"]].append(machine["machine_id"])
    for row in operations:
        minutes = float(row["processing_time_per_piece_min"]) * int(next(order["quantity"] for order in orders if order["order_id"] == row["order_id"]))
        by_capability[row["operation_type"]] += minutes / 60
        eligible = machine_by_type[row["required_machine_type"]]
        for machine_id in eligible:
            workload_by_machine[machine_id] += minutes / 60 / len(eligible)
    capacity = {row["machine_id"]: 14 * 2 * 7.5 for row in machines}
    workload_by_machine = {machine["machine_id"]: workload_by_machine.get(machine["machine_id"], 0.0) for machine in machines}
    ratios = {machine_id: round(workload / capacity[machine_id], 3) for machine_id, workload in workload_by_machine.items()}
    grinder_workload = sum(value for key, value in by_capability.items() if "GRINDING" in key)
    grinder_capacity = 14 * 2 * 7.5
    return {
        "orders": {"total": len(orders), "operations_total": len(operations), "operations_per_order": dict(Counter(sum(1 for op in operations if op["order_id"] == order["order_id"] and "." not in op["sequence"]) for order in orders)), "quantity_min": min(quantities), "quantity_max": max(quantities), "quantity_mean": round(sum(quantities) / len(quantities), 1)},
        "workload_hours_by_operation": {key: round(value, 2) for key, value in by_capability.items()},
        "workload_hours_by_machine": {key: round(value, 2) for key, value in workload_by_machine.items()},
        "capacity_hours_per_machine": 210.0,
        "demand_capacity_ratio_by_machine": ratios,
        "grinding": {"workload_hours": round(grinder_workload, 2), "capacity_hours": grinder_capacity, "ratio": round(grinder_workload / grinder_capacity, 3)},
        "operator_skill_coverage": dict(Counter(row["machine_type"] for row in skills)),
        "operator_workload_potential": {shift: sum(1 for row in operators if row["normal_shift"] == shift) for shift in ("MORNING", "AFTERNOON")},
        "changeover_distribution": dict(Counter(row["category"] for row in changeovers)),
        "maintenance_hours": round(sum(float(row["duration_hours"]) for row in maintenance), 2),
        "breakdowns": {"count": len(breakdowns), "duration_hours": {"min": min(float(row["duration_hours"]) for row in breakdowns), "max": max(float(row["duration_hours"]) for row in breakdowns), "mean": round(sum(float(row["duration_hours"]) for row in breakdowns) / len(breakdowns), 2)}},
        "quality": {"rework_events": len(reworks), "rework_piece_total": sum(int(row["failed_quantity"]) for row in reworks), "orders_with_rework": len({row["order_id"] for row in reworks}), "failure_rate_range_assumption": "2-5% of pieces at inspection; rework is a separate event"},
        "due_date_offsets_days": [round((__import__("datetime").datetime.fromisoformat(row["due_date"]) - PLANNING_START).total_seconds() / 86400, 1) for row in orders],
        "signals": {"potential_bottlenecks": ["GRINDER"], "underused_families": [key for key, value in ratios.items() if value < 0.1], "likely_infeasible": grinder_workload > grinder_capacity, "notes": "Capacity is a regular two-shift upper bound before setup, maintenance, breakdowns, or precedence effects."},
    }


if __name__ == "__main__":
    report = build_report()
    (Path("data") / "quality_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))