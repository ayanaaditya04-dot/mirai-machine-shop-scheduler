"""Hard integrity checks for the Mission 2 normalized dataset."""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from src.data_generator import FAMILIES, PLANNING_START, OUTPUT_TABLES

HORIZON_END = PLANNING_START.replace(day=15)
REQUIRED = {
    "machines": ["machine_id", "machine_type", "capabilities"],
    "operators": ["operator_id", "normal_shift"],
    "operator_skills": ["operator_id", "machine_type"],
    "shifts": ["shift_id", "start_time", "end_time"],
    "customers": ["customer_id"], "orders": ["order_id", "customer_id", "quantity"],
    "operations": ["operation_id", "order_id", "sequence", "required_machine_type"],
    "changeovers": ["from_family", "to_family", "changeover_time_min"],
    "maintenance": ["maintenance_id", "machine_id", "start_time", "end_time"],
    "breakdowns": ["breakdown_id", "machine_id", "start_time", "duration_hours"],
    "materials": ["material_id", "order_id", "available_date"],
    "rework_events": ["rework_id", "order_id", "original_operation_id", "rework_operation_id"],
}


def _read(directory: Path, table: str) -> list[dict[str, str]]:
    with (directory / f"{table}.csv").open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def validate_dataset(data_dir: str | Path = "data") -> list[str]:
    directory = Path(data_dir)
    errors: list[str] = []
    tables: dict[str, list[dict[str, str]]] = {}
    for table in OUTPUT_TABLES:
        path = directory / f"{table}.csv"
        if not path.exists():
            errors.append(f"missing table: {table}.csv")
            continue
        tables[table] = _read(directory, table)
        for column in REQUIRED[table]:
            if column not in tables[table][0] if tables[table] else True:
                errors.append(f"{table}: missing column {column}")
        id_column = next((column for column in tables[table][0] if column.endswith("_id")), None) if tables[table] and table != "operator_skills" else None
        if id_column:
            ids = [row.get(id_column, "") for row in tables[table]]
            if any(not value for value in ids):
                errors.append(f"{table}: null {id_column}")
            if len(ids) != len(set(ids)):
                errors.append(f"{table}: duplicate {id_column}")

    if len(tables.get("machines", [])) != 14:
        errors.append("machines: expected exactly 14")
    machines = {row["machine_id"]: row for row in tables.get("machines", [])}
    if sum(row.get("machine_type") == "GRINDER" for row in machines.values()) != 1:
        errors.append("machines: expected exactly one grinder")
    machine_types = {row.get("machine_type") for row in machines.values()}
    capabilities = {value for row in machines.values() for value in row.get("capabilities", "").split("|") if value}

    operators = {row["operator_id"]: row for row in tables.get("operators", [])}
    skills = tables.get("operator_skills", [])
    grinder_ops = {row.get("operator_id") for row in skills if row.get("machine_type") == "GRINDER"}
    if len(grinder_ops) != 3:
        errors.append("operator_skills: expected exactly 3 grinding-qualified operators")
    for row in skills:
        if row.get("operator_id") not in operators:
            errors.append(f"operator_skills: unknown operator {row.get('operator_id')}")
        if row.get("machine_type") not in machine_types:
            errors.append(f"operator_skills: unknown machine type {row.get('machine_type')}")
    for table, key, referenced in (("operator_skills", "operator_id", operators), ("maintenance", "machine_id", machines), ("breakdowns", "machine_id", machines)):
        for row in tables.get(table, []):
            if not row.get(key):
                errors.append(f"{table}: null {key}")
            elif row[key] not in referenced:
                errors.append(f"{table}: unknown {key} {row[key]}")

    customers = {row["customer_id"]: row for row in tables.get("customers", [])}
    orders = {row["order_id"]: row for row in tables.get("orders", [])}
    for row in tables.get("orders", []):
        if row.get("customer_id") not in customers:
            errors.append(f"orders: unknown customer {row.get('customer_id')}")
        try:
            if not 200 <= int(row["quantity"]) <= 5000:
                errors.append(f"orders: invalid quantity {row.get('order_id')}")
            datetime.fromisoformat(row["due_date"])
            datetime.fromisoformat(row["release_date"])
        except (KeyError, ValueError):
            errors.append(f"orders: invalid quantity/date {row.get('order_id')}")

    operations = {row["operation_id"]: row for row in tables.get("operations", [])}
    by_order: dict[str, list[dict]] = {}
    for row in tables.get("operations", []):
        if row.get("order_id") not in orders:
            errors.append(f"operations: unknown order {row.get('order_id')}")
        if row.get("required_machine_type") not in machine_types:
            errors.append(f"operations: unknown machine type {row.get('required_machine_type')}")
        elif not any(row["required_machine_type"] == machine["machine_type"] and row["operation_type"] in machine["capabilities"].split("|") for machine in machines.values()):
            errors.append(f"operations: no capable machine for {row.get('operation_id')}")
        by_order.setdefault(row.get("order_id"), []).append(row)
    for order_id, rows in by_order.items():
        base = sorted((row for row in rows if "." not in row["sequence"]), key=lambda row: int(row["sequence"]))
        sequences = [int(row["sequence"]) for row in base]
        if not 3 <= len(base) <= 6 or sequences != list(range(1, len(base) + 1)):
            errors.append(f"operations: order {order_id} must have contiguous 3-6 base steps")

    for row in tables.get("shifts", []):
        try:
            start, end = datetime.fromisoformat(row["start_time"]), datetime.fromisoformat(row["end_time"])
            if end <= start or float(row["available_hours"]) <= 0:
                errors.append(f"shifts: invalid interval {row.get('shift_id')}")
        except (KeyError, ValueError):
            errors.append(f"shifts: invalid date {row.get('shift_id')}")
    pairs = {(row.get("from_family"), row.get("to_family")) for row in tables.get("changeovers", [])}
    if pairs != {(left, right) for left in FAMILIES for right in FAMILIES}:
        errors.append("changeovers: expected complete family matrix")
    for row in tables.get("changeovers", []):
        if float(row["changeover_time_min"]) <= 0 or row.get("category") not in {"MINOR", "MEDIUM", "MAJOR"}:
            errors.append(f"changeovers: invalid row {row.get('from_family')}/{row.get('to_family')}")

    for table in ("maintenance", "breakdowns"):
        for row in tables.get(table, []):
            try:
                start = datetime.fromisoformat(row["start_time"])
                end = datetime.fromisoformat(row["end_time"]) if table == "maintenance" else start
                duration = float(row["duration_hours"])
                if duration <= 0 or start < PLANNING_START or start >= HORIZON_END or (table == "maintenance" and end <= start):
                    errors.append(f"{table}: invalid horizon/duration {row.get('machine_id')}")
            except (KeyError, ValueError):
                errors.append(f"{table}: invalid date/duration {row.get('machine_id')}")

    material_orders = {row.get("order_id") for row in tables.get("materials", [])}
    if material_orders != set(orders):
        errors.append("materials: must contain exactly one record per order")
    for row in tables.get("materials", []):
        if row.get("order_id") not in orders:
            errors.append(f"materials: unknown order {row.get('order_id')}")

    for row in tables.get("rework_events", []):
        original, rework = operations.get(row.get("original_operation_id")), operations.get(row.get("rework_operation_id"))
        try:
            if not original or not rework or original["order_id"] != row["order_id"] or rework["order_id"] != row["order_id"]:
                errors.append(f"rework: inconsistent references {row.get('rework_id')}")
            if int(row["failed_quantity"]) <= 0 or int(row["failed_quantity"]) > int(orders[row["order_id"]]["quantity"]):
                errors.append(f"rework: invalid failed quantity {row.get('rework_id')}")
            if original and rework and float(rework["sequence"]) <= float(original["sequence"]):
                errors.append(f"rework: must follow original operation {row.get('rework_id')}")
        except (KeyError, ValueError):
            errors.append(f"rework: malformed row {row.get('rework_id')}")
    return errors


if __name__ == "__main__":
    failures = validate_dataset()
    if failures:
        print("\n".join(failures))
        raise SystemExit(1)
    print("Dataset validation passed")