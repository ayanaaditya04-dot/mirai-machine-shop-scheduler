"""Hard checks for a generated baseline Schedule."""
from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path

from src.data_generator import PLANNING_START


def _rows(data_dir: Path, name: str) -> list[dict]:
    with (data_dir / f"{name}.csv").open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def validate_schedule(schedule, data_dir: str | Path = "data") -> list[str]:
    directory = Path(data_dir)
    errors = []
    machines = {row["machine_id"]: row for row in _rows(directory, "machines")}
    operators = {row["operator_id"]: row for row in _rows(directory, "operators")}
    skills = {(row["operator_id"], row["machine_type"]) for row in _rows(directory, "operator_skills")}
    operations = {row["operation_id"]: row for row in _rows(directory, "operations")}
    orders = {row["order_id"]: row for row in _rows(directory, "orders")}
    shifts = {row["shift_id"]: row for row in _rows(directory, "shifts")}
    maintenance = {machine: [] for machine in machines}
    for row in _rows(directory, "maintenance"):
        maintenance[row["machine_id"]].append((datetime.fromisoformat(row["start_time"]), datetime.fromisoformat(row["end_time"])))
    breakdowns = {machine: [] for machine in machines}
    for row in _rows(directory, "breakdowns"):
        start = datetime.fromisoformat(row["start_time"])
        breakdowns[row["machine_id"]].append((start, start + timedelta(hours=float(row["duration_hours"]))))
    seen = set()
    by_order = {}
    machine_intervals, operator_intervals = {}, {}
    for slot in schedule.slots:
        if slot.operation_id in seen:
            errors.append(f"duplicate operation {slot.operation_id}")
        seen.add(slot.operation_id)
        machine = machines.get(slot.machine_id)
        operator = operators.get(slot.operator_id)
        operation = operations.get(slot.operation_id)
        if operation is None and "_RW_" in slot.operation_id:
            operation = operations.get(slot.operation_id.split("_RW_", 1)[0])
        shift = shifts.get(slot.shift_id)
        if not machine or not operation or not operator or not shift:
            errors.append(f"unknown reference in {slot.slot_id}")
            continue
        setup_start = slot.start_time - timedelta(minutes=slot.setup_time_minutes)
        if machine["machine_type"] != operation["required_machine_type"] or operation["operation_type"] not in machine["capabilities"].split("|"):
            errors.append(f"capability mismatch {slot.operation_id}")
        if (slot.operator_id, machine["machine_type"]) not in skills:
            errors.append(f"unqualified operator {slot.operator_id} for {slot.operation_id}")
        if setup_start < datetime.fromisoformat(shift["start_time"]) or slot.end_time > datetime.fromisoformat(shift["end_time"]):
            errors.append(f"shift boundary violation {slot.slot_id}")
        if slot.start_time <= setup_start or slot.end_time <= slot.start_time:
            errors.append(f"invalid interval {slot.slot_id}")
        if any(setup_start < end and slot.end_time > start for start, end in maintenance[slot.machine_id]):
            errors.append(f"maintenance conflict {slot.slot_id}")
        if any(setup_start < end and slot.end_time > start for start, end in breakdowns[slot.machine_id]):
            errors.append(f"breakdown conflict {slot.slot_id}")
        machine_intervals.setdefault(slot.machine_id, []).append((setup_start, slot.end_time, slot.slot_id))
        operator_intervals.setdefault(slot.operator_id, []).append((setup_start, slot.end_time, slot.slot_id))
        by_order.setdefault(slot.order_id, []).append(slot)
    for resource, intervals in ([("machine", values) for values in machine_intervals.values()] + [("operator", values) for values in operator_intervals.values()]):
        intervals.sort()
        for previous, current in zip(intervals, intervals[1:]):
            if current[0] < previous[1]:
                errors.append(f"{resource} overlap {previous[2]} / {current[2]}")
    for order_id, rows in by_order.items():
        rows.sort(key=lambda slot: slot.sequence)
        for previous, current in zip(rows, rows[1:]):
            if current.start_time < previous.end_time:
                errors.append(f"precedence violation {order_id}")
    expected = {operation_id for operation_id, row in operations.items() if "." not in row["sequence"]}
    if expected - seen:
        errors.append(f"unscheduled operations: {len(expected - seen)}")
    return errors