"""Explainable continuous-time priority/list scheduler for Phase 2."""
from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from src.data.load import load_economics_config, load_shifts_config
from src.data_generator import PLANNING_START
from src.models import Schedule, ScheduleSlot

STRATEGIES = ("CHEAPEST", "MOST_ON_TIME", "MOST_ROBUST")
HORIZON_END = PLANNING_START + timedelta(days=14)
SETUP_FAMILY_MAP = {
    "TURNING": "SHAFT", "THREADING": "GEAR", "BORING": "SHAFT",
    "MILLING": "HOUSING", "DRILLING": "FLANGE", "GRINDING": "BUSH",
    "INSPECTION": "BRACKET", "REWORK": "GEAR",
}


@dataclass
class JobOperation:
    operation_id: str
    order_id: str
    sequence: float
    operation_type: str
    required_machine_type: str
    processing_time_per_piece_min: float
    setup_family: str


@dataclass
class Job:
    order_id: str
    customer_id: str
    tier: str
    due_date: datetime
    release_date: datetime
    material_available: datetime
    quantity: int
    order_value: float
    operations: list[JobOperation] = field(default_factory=list)


@dataclass
class Candidate:
    operation: JobOperation
    machine: dict
    operator: dict
    shift: dict
    setup_minutes: float
    start: datetime
    end: datetime
    changeover_cost: float
    components: dict[str, float]
    score: float = 0.0


def _read(data_dir: Path, name: str) -> list[dict]:
    with (data_dir / f"{name}.csv").open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def build_jobs(data_dir: str | Path = "data") -> list[Job]:
    directory = Path(data_dir)
    orders = _read(directory, "orders")
    customer_tiers = {row["customer_id"]: row["tier"] for row in _read(directory, "customers")}
    materials = {row["order_id"]: row for row in _read(directory, "materials")}
    operations = _read(directory, "operations")
    grouped: dict[str, list[JobOperation]] = {}
    for row in operations:
        grouped.setdefault(row["order_id"], []).append(JobOperation(
            row["operation_id"], row["order_id"], float(row["sequence"]), row["operation_type"],
            row["required_machine_type"], float(row["processing_time_per_piece_min"]), row["setup_changeover_family"],
        ))
    jobs = []
    for row in orders:
        base_operations = sorted((op for op in grouped[row["order_id"]] if not op.sequence % 1), key=lambda op: op.sequence)
        if not 3 <= len(base_operations) <= 6:
            raise ValueError(f"{row['order_id']} has {len(base_operations)} operations; expected 3-6")
        jobs.append(Job(row["order_id"], row["customer_id"], customer_tiers[row["customer_id"]],
                        datetime.fromisoformat(row["due_date"]), datetime.fromisoformat(row["release_date"]),
                        datetime.fromisoformat(materials[row["order_id"]]["available_date"]), int(row["quantity"]), float(row["order_value_inr"]), base_operations))
    return jobs


def _interval_free(intervals: list[tuple[datetime, datetime]], start: datetime, end: datetime) -> bool:
    return all(end <= busy_start or start >= busy_end for busy_start, busy_end in intervals)


def _next_free(intervals: list[tuple[datetime, datetime]], start: datetime, duration: timedelta) -> datetime:
    current = start
    for busy_start, busy_end in sorted(intervals):
        if current + duration <= busy_start:
            return current
        if current < busy_end:
            current = busy_end
    return current


def _matrix(data_dir: Path) -> dict[tuple[str, str], tuple[str, float, float]]:
    result = {}
    for row in _read(data_dir, "changeovers"):
        result[(row["from_family"], row["to_family"])] = (row["category"], float(row["changeover_time_min"]), float(row["test_piece_cost_inr"]))
    return result


def _shift_windows(data_dir: Path, config: dict) -> list[dict]:
    windows = _read(data_dir, "shifts")
    result = []
    for row in windows:
        if row["shift_type"] == "NIGHT" and not config["allow_night_overtime"]:
            continue
        row = dict(row)
        row["start"] = datetime.fromisoformat(row["start_time"])
        row["end"] = datetime.fromisoformat(row["end_time"])
        row["regular"] = row["is_regular_capacity"] == "true"
        if row["start"] < HORIZON_END and row["end"] > PLANNING_START:
            result.append(row)
    return sorted(result, key=lambda row: row["start"])


def _candidate(job: Job, operation: JobOperation, machine: dict, operator: dict, shifts: list[dict], machine_busy: dict, operator_busy: dict, last_family: dict, matrix: dict, maintenance: dict, breakdowns: dict, previous_completion: datetime, config: dict, strategy: str, overtime_usage: dict) -> Candidate | None:
    machine_id, operator_id = machine["machine_id"], operator["operator_id"]
    previous_family = SETUP_FAMILY_MAP.get(last_family.get(machine_id, ""), last_family.get(machine_id, ""))
    current_family = SETUP_FAMILY_MAP.get(operation.setup_family, operation.setup_family)
    family_transition = matrix.get((previous_family, current_family))
    setup_minutes = family_transition[1] if family_transition else float(config["initial_setup_minutes"])
    test_cost = family_transition[2] if family_transition else 0.0
    duration = timedelta(minutes=job.quantity * operation.processing_time_per_piece_min)
    setup = timedelta(minutes=setup_minutes)
    earliest = max(previous_completion, job.material_available, PLANNING_START)
    best = None
    for shift in shifts:
        if not shift["regular"] and operator["overtime_willing"] != "true":
            continue
        cursor = max(shift["start"], earliest)
        if cursor >= shift["end"]:
            continue
        while cursor < shift["end"]:
            total_time = setup + duration
            setup_start = max(cursor, _next_free(machine_busy[machine_id], cursor, total_time), _next_free(operator_busy[operator_id], cursor, total_time))
            production_start = setup_start + setup
            end = production_start + duration
            if setup_start < shift["start"] or end > shift["end"] or end > HORIZON_END:
                break
            blockers = [(busy_end, "resource") for busy_start, busy_end in machine_busy[machine_id] + operator_busy[operator_id] if setup_start < busy_end and end > busy_start]
            blockers += [(end_time, "maintenance") for start_time, end_time in maintenance.get(machine_id, []) if setup_start < end_time and end > start_time]
            blockers += [(start_time + timedelta(hours=float(duration_hours)), "breakdown") for start_time, duration_hours in breakdowns.get(machine_id, []) if setup_start < start_time + timedelta(hours=float(duration_hours)) and end > start_time]
            if blockers:
                cursor = max(end_time for end_time, _ in blockers)
                continue
            if not shift["regular"]:
                hours = duration.total_seconds() / 3600
                day_key = (operator_id, shift["date"])
                week_key = (operator_id, shift["start"].date().isocalendar().week)
                if overtime_usage.get(day_key, 0.0) + hours > float(config["overtime"]["max_overtime_hours_per_day"]):
                    break
                if overtime_usage.get(week_key, 0.0) + hours > float(config["overtime"]["max_overtime_hours_per_week"]):
                    break
            break
        else:
            continue
        if cursor >= shift["end"] or setup_start < shift["start"] or end > shift["end"] or end > HORIZON_END or blockers:
            continue
        if best is None or end < best.end:
            machine_rate, operator_rate = float(machine["hourly_rate_inr"]), float(operator["hourly_rate_inr"])
            hours = duration.total_seconds() / 3600
            changeover_cost = setup_minutes / 60 * (machine_rate + operator_rate) + test_cost
            lateness_hours = max(0.0, (end - job.due_date).total_seconds() / 3600)
            risk = 1 / max(float(machine["mtbf_hours"]), 1.0)
            components = {"machine_cost": hours * machine_rate, "operator_cost": hours * operator_rate, "changeover_cost": changeover_cost,
                          "lateness_cost": lateness_hours * job.order_value * (0.02 if job.tier == "TIER_1" else 0.01 if job.tier == "TIER_2" else 0.005) / 24,
                          "due_date_urgency": max(0.0, (job.due_date - end).total_seconds() / 3600), "tier_priority": {"TIER_1": 3.0, "TIER_2": 2.0, "TIER_3": 1.0}[job.tier],
                          "reliability_risk": risk * hours, "utilization_pressure": len(machine_busy[machine_id]), "slack": max(0.0, (job.due_date - end).total_seconds() / 3600)}
            best = Candidate(operation, machine, operator, shift, setup_minutes, production_start, end, changeover_cost, components)
    return best


def _score(candidate: Candidate, strategy: str, weights: dict) -> float:
    terms = weights[strategy]
    if strategy == "CHEAPEST":
        return sum(terms[key] * candidate.components[key] for key in ("machine_cost", "operator_cost", "changeover_cost", "lateness_cost"))
    if strategy == "MOST_ON_TIME":
        return terms["due_date_urgency"] * candidate.components["due_date_urgency"] - terms["tier_priority"] * candidate.components["tier_priority"] + terms["lateness_cost"] * candidate.components["lateness_cost"]
    return (terms["reliability_risk"] * candidate.components["reliability_risk"]
            + terms["bottleneck_pressure"] * candidate.components["bottleneck_pressure"]
            + terms["operator_scarcity"] * candidate.components["operator_scarcity"]
            + terms["alternative_resource_scarcity"] * candidate.components["alternative_resource_scarcity"]
            - terms["slack"] * candidate.components["slack"]
            + terms["changeover_cost"] * candidate.components["changeover_cost"])


def enrich_robust_components(candidate: Candidate, machine_rows: list[dict], operator_rows: list[dict], skills: set[tuple[str, str]], machine_busy: dict[str, list[tuple[datetime, datetime]]]) -> None:
    eligible_machines = [machine for machine in machine_rows if machine["machine_type"] == candidate.operation.required_machine_type and candidate.operation.operation_type in machine["capabilities"].split("|")]
    eligible_operators = [operator for operator in operator_rows if (operator["operator_id"], candidate.machine["machine_type"]) in skills]
    alternative_count = max(1, len(eligible_machines) * len(eligible_operators))
    machine_hours = sum((end - start).total_seconds() / 3600 for start, end in machine_busy[candidate.machine["machine_id"]])
    candidate.components["bottleneck_pressure"] = machine_hours / 210
    candidate.components["operator_scarcity"] = 1 / max(1, len(eligible_operators))
    candidate.components["alternative_resource_scarcity"] = 1 / alternative_count


def generate_schedule(strategy: str, data_dir: str | Path = "data") -> Schedule:
    if strategy not in STRATEGIES:
        raise ValueError(f"Unknown strategy {strategy}")
    directory = Path(data_dir)
    jobs = build_jobs(directory)
    machines, operators = _read(directory, "machines"), _read(directory, "operators")
    skills = {(row["operator_id"], row["machine_type"]) for row in _read(directory, "operator_skills")}
    maintenance, breakdowns = {}, {}
    for row in _read(directory, "maintenance"):
        maintenance.setdefault(row["machine_id"], []).append((datetime.fromisoformat(row["start_time"]), datetime.fromisoformat(row["end_time"])))
    for row in _read(directory, "breakdowns"):
        breakdowns.setdefault(row["machine_id"], []).append((datetime.fromisoformat(row["start_time"]), row["duration_hours"]))
    config = __import__("yaml").safe_load((Path(__file__).resolve().parents[2] / "config" / "scheduling.yaml").read_text())
    config["overtime"] = load_economics_config()["overtime"]
    shifts = _shift_windows(directory, config)
    matrix = _matrix(directory)
    weights = config["weights"]
    machine_busy, operator_busy, last_family, slots, overtime_usage = {m["machine_id"]: [] for m in machines}, {o["operator_id"]: [] for o in operators}, {}, [], {}
    completed: dict[str, datetime] = {}
    unscheduled = []
    while len(completed) < sum(len(job.operations) for job in jobs):
        ready = [(job, op) for job in jobs for op in job.operations if op.operation_id not in completed and (op.sequence == 1 or f"{job.order_id}_{op.sequence - 1:02.0f}" in completed)]
        # operation IDs are not sequence-derived safely; use explicit prior operation lookup.
        ready = []
        for job in jobs:
            for index, op in enumerate(job.operations):
                if op.operation_id not in completed and (index == 0 or job.operations[index - 1].operation_id in completed):
                    ready.append((job, op))
        if not ready:
            break
        candidates = []
        for job, operation in ready:
            predecessor = completed.get(job.operations[job.operations.index(operation) - 1].operation_id, job.release_date) if operation.sequence != 1 else job.release_date
            for machine in machines:
                if machine["machine_type"] != operation.required_machine_type or operation.operation_type not in machine["capabilities"].split("|"):
                    continue
                for operator in operators:
                    if (operator["operator_id"], machine["machine_type"]) not in skills:
                        continue
                    candidate = _candidate(job, operation, machine, operator, shifts, machine_busy, operator_busy, last_family, matrix, maintenance, breakdowns, predecessor, config, strategy, overtime_usage)
                    if candidate:
                        enrich_robust_components(candidate, machines, operators, skills, machine_busy)
                        candidate.score = _score(candidate, strategy, weights)
                        candidates.append((candidate, job))
        if not candidates:
            unscheduled.extend(op.operation_id for job, op in ready)
            break
        candidate, job = min(candidates, key=lambda pair: (pair[0].score, pair[0].end, pair[0].operation.operation_id))
        setup_start = candidate.start - timedelta(minutes=candidate.setup_minutes)
        machine_busy[candidate.machine["machine_id"]].append((setup_start, candidate.end))
        operator_busy[candidate.operator["operator_id"]].append((setup_start, candidate.end))
        if not candidate.shift["regular"]:
            overtime_hours = (candidate.end - candidate.start).total_seconds() / 3600
            overtime_usage[(candidate.operator["operator_id"], candidate.shift["date"])] = overtime_usage.get((candidate.operator["operator_id"], candidate.shift["date"]), 0.0) + overtime_hours
            week_key = (candidate.operator["operator_id"], candidate.shift["start"].date().isocalendar().week)
            overtime_usage[week_key] = overtime_usage.get(week_key, 0.0) + overtime_hours
        last_family[candidate.machine["machine_id"]] = candidate.operation.setup_family
        completed[candidate.operation.operation_id] = candidate.end
        hours = (candidate.end - candidate.start).total_seconds() / 3600
        operator_cost = hours * float(candidate.operator["hourly_rate_inr"])
        slot = ScheduleSlot(f"SLOT_{len(slots) + 1:03d}", candidate.machine["machine_id"], candidate.machine["machine_type"], candidate.operator["operator_id"], candidate.shift["shift_id"], job.order_id, candidate.operation.operation_id, candidate.operation.sequence, candidate.operation.setup_family, candidate.setup_minutes, candidate.start, candidate.end, machine_cost=hours * float(candidate.machine["hourly_rate_inr"]), operator_cost=operator_cost, changeover_cost=candidate.changeover_cost, explanation=f"Selected {candidate.machine['machine_id']} / {candidate.operator['operator_id']} at score {candidate.score:.2f}; setup {candidate.setup_minutes:.1f} min.", decision_log={"strategy": strategy, "score": candidate.score, "components": candidate.components})
        slots.append(slot)
    summaries = []
    economics = load_economics_config()
    shift_by_id = {shift["shift_id"]: shift for shift in shifts}
    first_multiplier = float(economics["overtime"]["multiplier_first_4h"])
    beyond_multiplier = float(economics["overtime"]["multiplier_beyond_4h"])
    for slot in slots:
        shift = shift_by_id[slot.shift_id]
        if not shift["regular"]:
            hours = (slot.end_time - slot.start_time).total_seconds() / 3600
            multiplier = first_multiplier if hours <= 4 else beyond_multiplier
            slot.overtime_cost = hours * float(next(operator["hourly_rate_inr"] for operator in operators if operator["operator_id"] == slot.operator_id)) * (multiplier - 1)
    for job in jobs:
        job_slots = [slot for slot in slots if slot.order_id == job.order_id]
        completion = max((slot.end_time for slot in job_slots), default=None)
        late_days = max(0.0, ((completion - job.due_date).total_seconds() / 86400)) if completion else None
        penalty = 0.0 if late_days is None else min(late_days * economics["late_penalty"][job.tier]["daily_rate_pct"] / 100 * job.order_value, economics["late_penalty"][job.tier]["cap_pct"] / 100 * job.order_value)
        summaries.append({"order_id": job.order_id, "customer_id": job.customer_id, "tier": job.tier, "due_date": job.due_date.isoformat(), "promised_completion_date": completion.isoformat() if completion else None, "late": bool(late_days), "late_days": round(late_days or 0, 3), "penalty_cost": round(penalty, 2)})
    totals = {"machine_cost": sum(slot.machine_cost for slot in slots), "operator_cost": sum(slot.operator_cost for slot in slots), "overtime_cost": sum(slot.overtime_cost for slot in slots), "changeover_cost": sum(slot.changeover_cost for slot in slots), "penalty_cost": sum(row["penalty_cost"] for row in summaries)}
    totals["total_cost"] = sum(totals.values())
    return Schedule(strategy, slots, summaries, {key: round(value, 2) for key, value in totals.items()}, unscheduled)


def schedule_dataframe(schedule: Schedule) -> pd.DataFrame:
    return pd.DataFrame([{**slot.__dict__, "start_time": slot.start_time.isoformat(), "end_time": slot.end_time.isoformat(), "decision_log": json.dumps(slot.decision_log, sort_keys=True)} for slot in schedule.slots])


def export_schedule(schedule: Schedule, output_dir: str | Path = "outputs") -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    name = schedule.strategy.lower()
    schedule_dataframe(schedule).to_csv(output / f"schedule_{name}.csv", index=False)
    pd.DataFrame(schedule.order_summary).to_csv(output / f"order_summary_{name}.csv", index=False)
    (output / f"cost_summary_{name}.json").write_text(json.dumps(schedule.cost_summary, indent=2) + "\n", encoding="utf-8")