"""Phase 3 disruption handling with frozen operational history.

The baseline scheduler remains the owner of normal scheduling.  This module
reuses its candidate and scoring primitives while reserving unaffected future
work, so replanning is incremental rather than a fresh baseline run.
"""
from __future__ import annotations

import copy
import csv
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from src.data.load import load_economics_config
from src.data_generator import PLANNING_START
from src.models import Disruption, DisruptionType, Schedule, ScheduleSlot
from src.scheduler.engine import (
    HORIZON_END, JobOperation, _candidate, _matrix, _score, _shift_windows,
    enrich_robust_components,
    build_jobs,
)


@dataclass
class OperationalState:
    current_time: datetime
    machine_available: dict[str, datetime] = field(default_factory=dict)
    operator_available: dict[str, datetime] = field(default_factory=dict)
    machine_breakdowns: dict[str, list[tuple[datetime, datetime]]] = field(default_factory=dict)
    operator_absences: dict[str, list[tuple[datetime, datetime]]] = field(default_factory=dict)
    material_available: dict[str, datetime] = field(default_factory=dict)
    completed_operations: set[str] = field(default_factory=set)
    in_progress_operations: set[str] = field(default_factory=set)
    pending_operations: set[str] = field(default_factory=set)
    machine_last_family: dict[str, str] = field(default_factory=dict)


@dataclass
class ReplanResult:
    schedule: Schedule
    state: OperationalState
    disruptions: list[Disruption]
    affected_operations: list[str]
    changes: list[dict] = field(default_factory=list)
    explanation: str = ""
    impact: dict = field(default_factory=dict)


def should_authorize_overtime(expected_penalty: float, incremental_overtime_cost: float) -> bool:
    """Authorize overtime only when its premium is cheaper than delay."""
    return incremental_overtime_cost < expected_penalty


def _rows(data_dir: Path, name: str) -> list[dict]:
    with (data_dir / f"{name}.csv").open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def snapshot(schedule: Schedule, current_time: datetime, data_dir: str | Path = "data") -> OperationalState:
    state = OperationalState(current_time)
    for slot in schedule.slots:
        if slot.end_time <= current_time:
            state.completed_operations.add(slot.operation_id)
        elif slot.start_time < current_time < slot.end_time:
            state.in_progress_operations.add(slot.operation_id)
        else:
            state.pending_operations.add(slot.operation_id)
        if slot.end_time <= current_time:
            state.machine_last_family[slot.machine_id] = slot.setup_family
    for row in _rows(Path(data_dir), "materials"):
        state.material_available[row["order_id"]] = datetime.fromisoformat(row["available_date"])
    return state


def _disruption(kind: DisruptionType, entity: str, when: datetime, hours: float, description: str) -> Disruption:
    return Disruption(f"DIS_{kind.value}_{entity}_{when:%Y%m%d%H%M}", kind, when, entity, hours, description)


def apply_breakdown(schedule: Schedule, machine_id: str, start_time: datetime, duration: float, current_time: datetime | None = None, data_dir: str | Path = "data") -> ReplanResult:
    when = current_time or start_time
    return reschedule(schedule, when, [_disruption(DisruptionType.MACHINE_BREAKDOWN, machine_id, start_time, duration, f"{machine_id} unavailable for {duration:g} hours")], data_dir)


def apply_operator_absent(schedule: Schedule, operator_id: str, start_time: datetime, duration: float, current_time: datetime | None = None, data_dir: str | Path = "data") -> ReplanResult:
    when = current_time or start_time
    return reschedule(schedule, when, [_disruption(DisruptionType.OPERATOR_ABSENCE, operator_id, start_time, duration, f"{operator_id} absent for {duration:g} hours")], data_dir)


def apply_material_late(schedule: Schedule, order_id: str, new_available_time: datetime, current_time: datetime | None = None, data_dir: str | Path = "data") -> ReplanResult:
    when = current_time or new_available_time
    disruption = _disruption(DisruptionType.MATERIAL_DELAY, order_id, new_available_time, 0, f"Material for {order_id} available at {new_available_time.isoformat()}")
    return reschedule(schedule, when, [disruption], data_dir)


def apply_rework(schedule: Schedule, order_id: str, rework_quantity: int, current_time: datetime | None = None, data_dir: str | Path = "data") -> ReplanResult:
    when = current_time or PLANNING_START
    disruption = _disruption(DisruptionType.REWORK_REQUIRED, order_id, when, 0, f"{rework_quantity} pieces require rework for {order_id}")
    return reschedule(schedule, when, [disruption], data_dir, rework_quantity)


def _overlap(left_start, left_end, right_start, right_end):
    return left_start < right_end and left_end > right_start


def _cost_from_slots(slots: list[ScheduleSlot], summaries: list[dict]) -> dict[str, float]:
    totals = {key: 0.0 for key in ("machine_cost", "operator_cost", "overtime_cost", "changeover_cost", "penalty_cost")}
    for slot in slots:
        for key in totals:
            if key != "penalty_cost":
                totals[key] += getattr(slot, key)
    totals["penalty_cost"] = sum(float(row.get("penalty_cost", 0)) for row in summaries)
    totals["total_cost"] = sum(totals.values())
    return {key: round(value, 2) for key, value in totals.items()}


def reschedule(schedule: Schedule, current_time: datetime, disruptions: list[Disruption], data_dir: str | Path = "data", rework_quantity: int | None = None) -> ReplanResult:
    directory = Path(data_dir)
    state = snapshot(schedule, current_time, directory)
    old_slots = copy.deepcopy(schedule.slots)
    frozen = [slot for slot in old_slots if slot.operation_id in state.completed_operations or slot.operation_id in state.in_progress_operations]
    future = [slot for slot in old_slots if slot.operation_id in state.pending_operations]
    affected = set()
    operation_order = {slot.operation_id: slot.order_id for slot in old_slots}
    machine_rows = _rows(directory, "machines")
    operator_rows = _rows(directory, "operators")
    for disruption in disruptions:
        start = disruption.timestamp
        end = start + timedelta(hours=disruption.duration_hours)
        if disruption.type == DisruptionType.MACHINE_BREAKDOWN:
            state.machine_breakdowns.setdefault(disruption.affected_entity_id, []).append((start, end))
            affected |= {slot.operation_id for slot in future if slot.machine_id == disruption.affected_entity_id and _overlap(slot.start_time - timedelta(minutes=slot.setup_time_minutes), slot.end_time, start, end)}
        elif disruption.type == DisruptionType.OPERATOR_ABSENCE:
            state.operator_absences.setdefault(disruption.affected_entity_id, []).append((start, end))
            affected |= {slot.operation_id for slot in future if slot.operator_id == disruption.affected_entity_id and _overlap(slot.start_time - timedelta(minutes=slot.setup_time_minutes), slot.end_time, start, end)}
        elif disruption.type == DisruptionType.MATERIAL_DELAY:
            state.material_available[disruption.affected_entity_id] = disruption.timestamp
            affected |= {slot.operation_id for slot in future if slot.order_id == disruption.affected_entity_id}
        elif disruption.type == DisruptionType.REWORK_REQUIRED:
            affected |= {slot.operation_id for slot in future if slot.order_id == disruption.affected_entity_id}
    affected_orders = {operation_order[operation_id] for operation_id in affected}
    # A moved operation changes the feasible completion time of all later steps.
    for slot in future:
        if slot.order_id in affected_orders and slot.sequence >= min((s.sequence for s in future if s.operation_id in affected and s.order_id == slot.order_id), default=999):
            affected.add(slot.operation_id)

    jobs = {job.order_id: job for job in build_jobs(directory)}
    for order_id, available_time in state.material_available.items():
        if order_id in jobs:
            jobs[order_id].material_available = available_time
    if rework_quantity and disruptions and disruptions[-1].type == DisruptionType.REWORK_REQUIRED:
        job = jobs[disruptions[-1].affected_entity_id]
        original = job.operations[-2]
        rework = JobOperation(f"{original.operation_id}_RW_{rework_quantity}", job.order_id, original.sequence + 0.5, original.operation_type, original.required_machine_type, original.processing_time_per_piece_min * rework_quantity / job.quantity, "REWORK")
        job.operations.insert(-1, rework)
        affected.add(rework.operation_id)
        affected_orders.add(job.order_id)

    unaffected = [slot for slot in future if slot.operation_id not in affected]
    machine_busy = {row["machine_id"]: [] for row in machine_rows}
    operator_busy = {row["operator_id"]: [] for row in operator_rows}
    last_family = dict(state.machine_last_family)
    for slot in frozen + unaffected:
        setup_start = slot.start_time - timedelta(minutes=slot.setup_time_minutes)
        machine_busy[slot.machine_id].append((setup_start, slot.end_time))
        operator_busy[slot.operator_id].append((setup_start, slot.end_time))
        if slot.end_time <= current_time or slot in unaffected:
            last_family[slot.machine_id] = slot.setup_family
    maintenance, breakdowns = {}, {}
    for row in _rows(directory, "maintenance"):
        maintenance.setdefault(row["machine_id"], []).append((datetime.fromisoformat(row["start_time"]), datetime.fromisoformat(row["end_time"])))
    for row in _rows(directory, "breakdowns"):
        start = datetime.fromisoformat(row["start_time"])
        breakdowns.setdefault(row["machine_id"], []).append((start, row["duration_hours"]))
    for machine_id, intervals in state.machine_breakdowns.items():
        breakdowns.setdefault(machine_id, []).extend((start, (end - start).total_seconds() / 3600) for start, end in intervals)
    for operator_id, intervals in state.operator_absences.items():
        operator_busy.setdefault(operator_id, []).extend(intervals)
    config = __import__("yaml").safe_load((Path(__file__).resolve().parents[2] / "config" / "scheduling.yaml").read_text())
    config["overtime"] = load_economics_config()["overtime"]
    shifts = _shift_windows(directory, config)
    matrix = _matrix(directory)
    weights = config["weights"]
    pending = []
    for job in jobs.values():
        if job.order_id not in affected_orders:
            continue
        for operation in job.operations:
            if operation.operation_id in state.completed_operations or operation.operation_id in state.in_progress_operations:
                continue
            if operation.operation_id in affected or operation.operation_id not in {slot.operation_id for slot in future}:
                pending.append((job, operation))
    completed = {slot.operation_id: slot.end_time for slot in frozen + unaffected}
    changes = []
    generated = []
    while pending:
        ready = [(job, op) for job, op in pending if op.sequence == 1 or (job.operations[job.operations.index(op) - 1].operation_id in completed)]
        if not ready:
            break
        candidates = []
        for job, operation in ready:
            index = job.operations.index(operation)
            predecessor = completed.get(job.operations[index - 1].operation_id, job.release_date) if index else job.release_date
            for machine in machine_rows:
                if machine["machine_type"] != operation.required_machine_type or operation.operation_type not in machine["capabilities"].split("|"):
                    continue
                for operator in operator_rows:
                    if not any(row["operator_id"] == operator["operator_id"] and row["machine_type"] == machine["machine_type"] for row in _rows(directory, "operator_skills")):
                        continue
                    candidate = _candidate(job, operation, machine, operator, shifts, machine_busy, operator_busy, last_family, matrix, maintenance, breakdowns, max(predecessor, current_time), config, schedule.strategy, {})
                    if candidate:
                        enrich_robust_components(candidate, machine_rows, operator_rows, {(row["operator_id"], row["machine_type"]) for row in _rows(directory, "operator_skills")}, machine_busy)
                        if not candidate.shift["regular"]:
                            hours = (candidate.end - candidate.start).total_seconds() / 3600
                            multiplier = float(config["overtime"]["multiplier_first_4h"] if hours <= 4 else config["overtime"]["multiplier_beyond_4h"])
                            incremental_overtime_cost = hours * float(operator["hourly_rate_inr"]) * (multiplier - 1)
                            expected_penalty = candidate.components["lateness_cost"]
                            if not should_authorize_overtime(expected_penalty, incremental_overtime_cost):
                                continue
                        candidate.score = _score(candidate, schedule.strategy, weights)
                        candidates.append((candidate, job))
        if not candidates:
            break
        candidate, job = min(candidates, key=lambda pair: (pair[0].score, pair[0].end, pair[0].operation.operation_id))
        setup_start = candidate.start - timedelta(minutes=candidate.setup_minutes)
        machine_busy[candidate.machine["machine_id"]].append((setup_start, candidate.end))
        operator_busy[candidate.operator["operator_id"]].append((setup_start, candidate.end))
        last_family[candidate.machine["machine_id"]] = candidate.operation.setup_family
        completed[candidate.operation.operation_id] = candidate.end
        pending.remove((job, candidate.operation))
        hours = (candidate.end - candidate.start).total_seconds() / 3600
        slot = ScheduleSlot(f"REPLAN_{len(changes) + 1:03d}", candidate.machine["machine_id"], candidate.machine["machine_type"], candidate.operator["operator_id"], candidate.shift["shift_id"], job.order_id, candidate.operation.operation_id, candidate.operation.sequence, candidate.operation.setup_family, candidate.setup_minutes, candidate.start, candidate.end, explanation=f"Replanned after {', '.join(d.type.value for d in disruptions)}; selected {candidate.machine['machine_id']} / {candidate.operator['operator_id']}.", decision_log={"replan": True, "score": candidate.score, "components": candidate.components})
        slot.machine_cost = hours * float(candidate.machine["hourly_rate_inr"])
        slot.operator_cost = hours * float(candidate.operator["hourly_rate_inr"])
        slot.changeover_cost = candidate.changeover_cost
        if not candidate.shift["regular"]:
            multiplier = float(config["overtime"]["multiplier_first_4h"] if hours <= 4 else config["overtime"]["multiplier_beyond_4h"])
            slot.overtime_cost = slot.operator_cost * (multiplier - 1)
        generated.append(slot)
        changes.append({"operation_id": slot.operation_id, "order_id": slot.order_id, "old_machine_id": next((old.machine_id for old in old_slots if old.operation_id == slot.operation_id), None), "new_machine_id": slot.machine_id, "old_start_time": next((old.start_time.isoformat() for old in old_slots if old.operation_id == slot.operation_id), None), "new_start_time": slot.start_time.isoformat()})
    final_slots = frozen + unaffected + generated
    result_schedule = copy.deepcopy(schedule)
    result_schedule.slots = sorted(final_slots, key=lambda slot: (slot.start_time, slot.slot_id))
    result_schedule.unscheduled_operations = [op.operation_id for job, op in pending]
    result_schedule.order_summary = _rebuild_order_summary(result_schedule, directory)
    result_schedule.cost_summary = _cost_from_slots(result_schedule.slots, result_schedule.order_summary)
    explanation = _explain(disruptions, changes, result_schedule)
    return ReplanResult(result_schedule, state, disruptions, sorted(affected), changes, explanation, compare_schedules(schedule, result_schedule, current_time))


def _explain(disruptions, changes, schedule):
    lines = ["DISRUPTION", *[f"{d.timestamp:%Y-%m-%d %H:%M}: {d.description}" for d in disruptions], "", "IMPACT", f"{len(changes)} operations replanned", "", "CHANGES"]
    lines.extend(f"{c['operation_id']}: {c['old_machine_id'] or 'new'} -> {c['new_machine_id']} ({c['old_start_time'] or 'new'} -> {c['new_start_time']})" for c in changes)
    lines += ["", "COST", f"Incremental disruption cost: ₹{schedule.cost_summary['total_cost']:.2f}", "", "RECOMMENDATION", "Protect Tier-1 work first; authorize overtime only when its configured premium is below delivery exposure."]
    return "\n".join(lines)


def _rebuild_order_summary(schedule: Schedule, data_dir: Path) -> list[dict]:
    orders = {row["order_id"]: row for row in _rows(data_dir, "orders")}
    customer_tiers = {row["customer_id"]: row["tier"] for row in _rows(data_dir, "customers")}
    economics = load_economics_config()
    summary = []
    for order_id, order in orders.items():
        slots = [slot for slot in schedule.slots if slot.order_id == order_id]
        completion = max((slot.end_time for slot in slots), default=None)
        due = datetime.fromisoformat(order["due_date"])
        late_days = max(0.0, (completion - due).total_seconds() / 86400) if completion else 0.0
        tier = customer_tiers[order["customer_id"]]
        value = float(order["order_value_inr"])
        penalty = min(late_days * economics["late_penalty"][tier]["daily_rate_pct"] / 100 * value, economics["late_penalty"][tier]["cap_pct"] / 100 * value)
        summary.append({"order_id": order_id, "customer_id": order["customer_id"], "tier": tier, "due_date": order["due_date"], "promised_completion_date": completion.isoformat() if completion else None, "late": bool(late_days), "late_days": round(late_days, 3), "penalty_cost": round(penalty, 2)})
    return summary


def compare_schedules(old_schedule: Schedule, new_schedule: Schedule, current_time: datetime) -> dict:
    old = {slot.operation_id: slot for slot in old_schedule.slots if slot.start_time >= current_time}
    new = {slot.operation_id: slot for slot in new_schedule.slots if slot.start_time >= current_time}
    common = set(old) & set(new)
    moved = [operation_id for operation_id in common if (old[operation_id].machine_id, old[operation_id].operator_id, old[operation_id].shift_id, old[operation_id].start_time) != (new[operation_id].machine_id, new[operation_id].operator_id, new[operation_id].shift_id, new[operation_id].start_time)]
    wasted = []
    for slot in old_schedule.slots:
        setup_start = slot.start_time - timedelta(minutes=slot.setup_time_minutes)
        if setup_start < current_time and slot.operation_id in old and (slot.operation_id not in new or slot.operation_id in moved):
            wasted.append({"operation_id": slot.operation_id, "setup_minutes": slot.setup_time_minutes, "setup_cost": slot.changeover_cost, "reason": "setup began before disruption and became unusable after the operation moved"})
    old_summary = {row["order_id"]: row for row in old_schedule.order_summary}
    new_summary = {row["order_id"]: row for row in new_schedule.order_summary}
    delivery = [{"order_id": order_id, "old_completion": old_summary.get(order_id, {}).get("promised_completion_date"), "new_completion": new_summary.get(order_id, {}).get("promised_completion_date")} for order_id in new_summary if old_summary.get(order_id, {}).get("promised_completion_date") != new_summary[order_id].get("promised_completion_date")]
    old_overtime_hours = sum((slot.end_time - slot.start_time).total_seconds() / 3600 for slot in old_schedule.slots if slot.start_time >= current_time and slot.shift_id.endswith("_NIGHT"))
    new_overtime_hours = sum((slot.end_time - slot.start_time).total_seconds() / 3600 for slot in new_schedule.slots if slot.start_time >= current_time and slot.shift_id.endswith("_NIGHT"))
    old_future_cost = sum(slot.machine_cost + slot.operator_cost + slot.overtime_cost + slot.changeover_cost for slot in old_schedule.slots if slot.start_time >= current_time)
    new_future_cost = sum(slot.machine_cost + slot.operator_cost + slot.overtime_cost + slot.changeover_cost for slot in new_schedule.slots if slot.start_time >= current_time)
    old_penalty = sum(float(row.get("penalty_cost", 0)) for row in old_schedule.order_summary)
    new_penalty = sum(float(row.get("penalty_cost", 0)) for row in new_schedule.order_summary)
    wasted_cost = sum(item["setup_cost"] for item in wasted)
    return {"sunk_historical_cost": round(sum(slot.machine_cost + slot.operator_cost + slot.overtime_cost + slot.changeover_cost for slot in old_schedule.slots if slot.end_time <= current_time), 2), "operations_moved": len(moved), "moved_operation_ids": moved, "machine_changes": sum(old[operation_id].machine_id != new[operation_id].machine_id for operation_id in moved), "operator_changes": sum(old[operation_id].operator_id != new[operation_id].operator_id for operation_id in moved), "shift_changes": sum(old[operation_id].shift_id != new[operation_id].shift_id for operation_id in moved), "delivery_changes": delivery, "additional_overtime_hours": round(new_overtime_hours - old_overtime_hours, 2), "additional_overtime_cost": round(sum(slot.overtime_cost for slot in new_schedule.slots if slot.start_time >= current_time) - sum(slot.overtime_cost for slot in old_schedule.slots if slot.start_time >= current_time), 2), "additional_penalty_cost": round(new_penalty - old_penalty, 2), "wasted_changeover_time_minutes": round(sum(item["setup_minutes"] for item in wasted), 2), "wasted_changeover_cost": round(wasted_cost, 2), "incremental_disruption_cost": round(new_future_cost - old_future_cost + new_penalty - old_penalty + wasted_cost, 2), "wasted_changeover": wasted}