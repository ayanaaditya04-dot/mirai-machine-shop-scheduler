"""Deterministic Mission 2 dataset generator.

The generator writes normalized CSV tables.  Numerical operating assumptions are
kept in config/ and the planning start is explicit rather than derived from the
clock, so the same inputs always produce the same files.
"""
from __future__ import annotations

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

from src.data.customers import generate_customers
from src.data.load import load_all
from src.data.machines_gen import generate_machines
from src.data.operators_gen import generate_operators
from src.data.seed_data import PART_CATALOG, SEED
from src.models import MachineType, Operation

PLANNING_START = datetime(2026, 9, 1, 0, 0)
OUTPUT_TABLES = (
    "machines", "operators", "operator_skills", "shifts", "customers", "orders",
    "operations", "changeovers", "maintenance", "breakdowns", "materials", "rework_events",
)

CAPABILITIES = {
    Operation.TURNING: MachineType.CNC_LATHE,
    Operation.FACING: MachineType.CNC_LATHE,
    Operation.THREADING: MachineType.CNC_LATHE,
    Operation.BORING: MachineType.CNC_LATHE,
    Operation.MILLING: MachineType.CNC_VMC,
    Operation.DRILLING: MachineType.RADIAL_DRILL,
    Operation.TAPPING: MachineType.CNC_VMC,
    Operation.REAMING: MachineType.RADIAL_DRILL,
    Operation.SURFACE_GRINDING: MachineType.GRINDER,
    Operation.CYLINDRICAL_GRINDING: MachineType.GRINDER,
    Operation.INSPECTION: MachineType.CMM_INSPECTION,
}
MATERIALS = ["MILD_STEEL", "EN8", "EN24", "EN31", "STAINLESS_STEEL_304", "ALUMINIUM_6061", "CAST_IRON"]
FAMILIES = ["SHAFT", "HOUSING", "FLANGE", "BUSH", "BRACKET", "GEAR"]
CAUSES = ["tool_failure", "electrical_fault", "hydraulic_leak", "spindle_vibration", "coolant_failure"]


def _write(path: Path, name: str, rows: list[dict], fields: list[str]) -> None:
    with (path / f"{name}.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _operation_plan(index: int) -> list[tuple[Operation, str]]:
    plans = [
        [(Operation.TURNING, "TURNING"), (Operation.MILLING, "MILLING"), (Operation.DRILLING, "DRILLING"), (Operation.CYLINDRICAL_GRINDING, "GRINDING"), (Operation.INSPECTION, "INSPECTION")],
        [(Operation.FACING, "TURNING"), (Operation.TURNING, "TURNING"), (Operation.THREADING, "THREADING"), (Operation.SURFACE_GRINDING, "GRINDING"), (Operation.INSPECTION, "INSPECTION")],
        [(Operation.MILLING, "MILLING"), (Operation.DRILLING, "DRILLING"), (Operation.TAPPING, "THREADING"), (Operation.SURFACE_GRINDING, "GRINDING"), (Operation.INSPECTION, "INSPECTION")],
        [(Operation.TURNING, "TURNING"), (Operation.BORING, "BORING"), (Operation.MILLING, "MILLING"), (Operation.DRILLING, "DRILLING"), (Operation.SURFACE_GRINDING, "GRINDING"), (Operation.INSPECTION, "INSPECTION")],
        [(Operation.FACING, "TURNING"), (Operation.MILLING, "MILLING"), (Operation.REAMING, "DRILLING"), (Operation.CYLINDRICAL_GRINDING, "GRINDING"), (Operation.INSPECTION, "INSPECTION")],
    ]
    return plans[index % len(plans)]


def generate_dataset(output_dir: str | Path = "data") -> Path:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    cfg = load_all()
    rng = random.Random(SEED)
    machines = generate_machines(cfg["machines"], PLANNING_START)
    operators = generate_operators(cfg["operators"], cfg["economics"])
    customers = generate_customers(cfg["customers_orders"])

    machine_by_type: dict[MachineType, list[str]] = {}
    for machine in machines:
        machine_by_type.setdefault(machine.machine_type, []).append(machine.machine_id)

    # Complete non-grinder coverage for both regular rosters while preserving the
    # hard exactly-three grinder qualification constraint from the assignment.
    machine_id_to_type = {machine.machine_id: machine.machine_type for machine in machines}

    def normalize_machine_type(value):
        if isinstance(value, MachineType):
            return value
        if value in machine_id_to_type:
            return machine_id_to_type[value]
        return MachineType(value)

    qualifications = {
        operator.operator_id: {
            normalize_machine_type(value)
            for value in operator.qualified_machines
        }
        for operator in operators
    }
    for type_index, machine_type in enumerate(machine_by_type):
        if machine_type == MachineType.GRINDER:
            continue
        for shift_index in (0, 1):
            operator = operators[(type_index * 2 + shift_index) % len(operators)]
            qualifications[operator.operator_id].add(machine_type)

    machine_rows = []
    maintenance_rows = []
    for machine in machines:
        machine_rows.append({
            "machine_id": machine.machine_id, "name": machine.name, "machine_type": machine.machine_type.value,
            "capabilities": "|".join(sorted(cap.value for cap in machine.capabilities)),
            "hourly_rate_inr": str(machine.hourly_rate_inr), "max_regular_shifts_per_day": machine.max_shifts_per_day,
            "mtbf_hours": machine.mtbf_hours, "mttr_hours": machine.mttr_hours, "status": machine.status.value,
        })
        window = machine.planned_maintenance_windows[0]
        maintenance_rows.append({"maintenance_id": f"MNT_{len(maintenance_rows) + 1:03d}", "machine_id": machine.machine_id,
                                  "start_time": window.start.isoformat(), "end_time": window.end.isoformat(),
                                  "duration_hours": (window.end - window.start).total_seconds() / 3600})

    operator_rows = []
    skill_rows = []
    for index, operator in enumerate(operators):
        shift = "MORNING" if index % 2 == 0 else "AFTERNOON"
        operator_rows.append({"operator_id": operator.operator_id, "name": operator.name, "normal_shift": shift,
                              "skill_level": operator.skill_level.value, "hourly_rate_inr": str(operator.hourly_rate_inr),
                              "overtime_willing": str(operator.overtime_willing).lower()})
        for machine_type in sorted(qualifications[operator.operator_id], key=lambda value: value.value):
            skill_rows.append({"operator_id": operator.operator_id, "machine_type": machine_type.value, "skill_level": operator.skill_level.value})

    shift_rows = []
    for day in range(14):
        date = PLANNING_START.date() + timedelta(days=day)
        for shift_type, start_hour, end_hour, productive, regular in (("MORNING", 6, 14, 7.5, True), ("AFTERNOON", 14, 22, 7.5, True), ("NIGHT", 22, 30, 7.0, False)):
            start = PLANNING_START.replace(year=date.year, month=date.month, day=date.day, hour=start_hour % 24)
            if end_hour == 30:
                end = start + timedelta(hours=8)
            else:
                end = start.replace(hour=end_hour)
            shift_rows.append({"shift_id": f"SH_{day + 1:02d}_{shift_type}", "date": str(date), "shift_type": shift_type,
                               "start_time": start.isoformat(), "end_time": end.isoformat(), "available_hours": productive,
                               "is_regular_capacity": str(regular).lower(), "premium_multiplier": 1.0 if regular else 1.5})

    order_rows, operation_rows, material_rows, rework_rows = [], [], [], []
    operation_lookup = {}
    for index in range(25):
        customer = customers[index % len(customers)]
        quantity_lo, quantity_hi = cfg["customers_orders"]["quantity_range"]
        quantity = rng.randint(quantity_lo, quantity_hi)
        release = PLANNING_START + timedelta(days=rng.randint(0, 2))
        band_counts = cfg["customers_orders"]["due_date_band_order_counts"]
        if index < band_counts["comfortable"]:
            due_band = "comfortable"
        elif index < band_counts["comfortable"] + band_counts["moderate"]:
            due_band = "moderate"
        else:
            due_band = "tight"
        if customer.tier.value == "TIER_1" and index % 2 == 1:
            due_band = "tight"
        due_lo, due_hi = cfg["customers_orders"]["due_date_bands_days"][due_band]
        due = PLANNING_START + timedelta(days=rng.randint(due_lo, due_hi), hours=rng.choice((0, 6, 12)))
        material = MATERIALS[index % len(MATERIALS)]
        plan = _operation_plan(index)
        order_id = f"ORD_{index + 1:03d}"
        value = quantity * sum(rng.uniform(0.02, 0.08) for _ in plan) * 950
        order_rows.append({"order_id": order_id, "customer_id": customer.customer_id, "part_name": PART_CATALOG[index],
                           "part_number": f"SPW-{index + 1:03d}", "part_family": FAMILIES[index % len(FAMILIES)],
                           "quantity": quantity, "release_date": release.date().isoformat(), "due_date": due.isoformat(),
                           "material": material, "priority": 3 if customer.tier.value == "TIER_1" else (2 if customer.tier.value == "TIER_2" else 1),
                           "order_value_inr": round(value, 2), "status": "PENDING"})
        for seq, (operation, family) in enumerate(plan, 1):
            op_id = f"OPR_{index + 1:03d}_{seq:02d}"
            if operation in (Operation.SURFACE_GRINDING, Operation.CYLINDRICAL_GRINDING):
                duration_lo, duration_hi = cfg["customers_orders"]["grinding_duration_range_hours"]
                per_piece = round(rng.uniform(duration_lo, duration_hi) * 60 / quantity, 5)
            else:
                per_piece = round(rng.uniform(0.018, 0.075), 3)
            operation_lookup[op_id] = (order_id, seq)
            operation_rows.append({"operation_id": op_id, "order_id": order_id, "sequence": seq, "operation_type": operation.value,
                                   "required_machine_type": CAPABILITIES[operation].value, "processing_time_per_piece_min": per_piece,
                                   "setup_changeover_family": family, "quality_check_required": str(operation == Operation.INSPECTION).lower()})
        material_rows.append({"material_id": f"MAT_{index + 1:03d}", "order_id": order_id, "material_type": material,
                              "available_date": (release + timedelta(days=(index % 4))).date().isoformat()})
        if index % 4 == 1:
            failed_seq = len(plan) - 2
            rework_id = f"RW_{index + 1:03d}"
            original = f"OPR_{index + 1:03d}_{failed_seq:02d}"
            rework_rows.append({"rework_id": rework_id, "order_id": order_id, "original_operation_id": original,
                                "failed_quantity": max(1, round(quantity * (0.02 + (index % 4) * 0.01))),
                                "rework_operation_id": original + "_RW"})
            operation_rows.append({"operation_id": original + "_RW", "order_id": order_id, "sequence": failed_seq + 0.5,
                                   "operation_type": operation_rows[-1]["operation_type"], "required_machine_type": operation_rows[-1]["required_machine_type"],
                                   "processing_time_per_piece_min": operation_rows[-1]["processing_time_per_piece_min"], "setup_changeover_family": "REWORK",
                                   "quality_check_required": "true"})

    breakdown_rows = []
    for index, machine in enumerate(machines):
        count = 1 + (index % 3 == 0) + (index % 7 == 0)
        for event in range(count):
            start = PLANNING_START + timedelta(days=1 + ((index * 3 + event * 5) % 12), hours=2 + event * 7)
            duration = 2 + ((index + event * 3) % 11)
            breakdown_rows.append({"breakdown_id": f"BD_{len(breakdown_rows) + 1:03d}", "machine_id": machine.machine_id,
                                  "start_time": start.isoformat(), "duration_hours": duration, "cause": CAUSES[(index + event) % len(CAUSES)]})

    changeover_rows = []
    categories = {"MINOR": (15, 30), "MEDIUM": (35, 60), "MAJOR": (75, 150)}
    for from_family in FAMILIES:
        for to_family in FAMILIES:
            category = "MINOR" if from_family == to_family else ("MEDIUM" if from_family[0] == to_family[0] else "MAJOR")
            lo, hi = categories[category]
            changeover_rows.append({"from_family": from_family, "to_family": to_family, "category": category,
                                    "changeover_time_min": rng.randint(lo, hi), "test_piece_cost_inr": 0 if category == "MINOR" else (150 if category == "MEDIUM" else 300)})

    _write(output, "machines", machine_rows, list(machine_rows[0]))
    _write(output, "operators", operator_rows, list(operator_rows[0]))
    _write(output, "operator_skills", skill_rows, ["operator_id", "machine_type", "skill_level"])
    _write(output, "shifts", shift_rows, list(shift_rows[0]))
    _write(output, "customers", [{"customer_id": c.customer_id, "name": c.name, "tier": c.tier.value, "revenue_share": c.revenue_share,
                                   "just_in_time": str(c.just_in_time).lower(), "late_penalty_pct_per_day": c.late_penalty_pct,
                                   "relationship_years": c.relationship_years} for c in customers], ["customer_id", "name", "tier", "revenue_share", "just_in_time", "late_penalty_pct_per_day", "relationship_years"])
    _write(output, "orders", order_rows, list(order_rows[0]))
    _write(output, "operations", operation_rows, list(operation_rows[0]))
    _write(output, "changeovers", changeover_rows, list(changeover_rows[0]))
    _write(output, "maintenance", maintenance_rows, list(maintenance_rows[0]))
    _write(output, "breakdowns", breakdown_rows, list(breakdown_rows[0]))
    _write(output, "materials", material_rows, list(material_rows[0]))
    _write(output, "rework_events", rework_rows, list(rework_rows[0]))
    return output


if __name__ == "__main__":
    generate_dataset()