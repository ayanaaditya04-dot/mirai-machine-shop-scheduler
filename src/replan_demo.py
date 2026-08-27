"""Run representative Phase 3 scenarios and export their evidence."""
from datetime import datetime, timedelta
from pathlib import Path
import json
import time

from src.replanner import apply_breakdown, apply_material_late, apply_operator_absent, apply_rework, reschedule
from src.models import Disruption, DisruptionType
from src.scheduler.engine import export_schedule, generate_schedule
from src.validation.schedule_validator import validate_schedule


def main():
    output = Path("outputs")
    baseline = generate_schedule("MOST_ON_TIME")
    current = datetime.fromisoformat("2026-09-03T06:00:00")
    grinder = next(slot for slot in baseline.slots if slot.machine_id == "GRINDER_01" and slot.start_time > current)
    operator = next(slot for slot in baseline.slots if slot.operator_id == "OP_001" and slot.start_time > current)
    scenarios = {
        "breakdown": lambda: apply_breakdown(baseline, grinder.machine_id, grinder.start_time - timedelta(minutes=5), 8, current),
        "operator_absence": lambda: apply_operator_absent(baseline, operator.operator_id, operator.start_time - timedelta(minutes=5), 8, current),
        "material_delay": lambda: apply_material_late(baseline, "ORD_008", current + timedelta(days=1), current),
        "rework": lambda: apply_rework(baseline, "ORD_008", 40, current),
        "cascade": lambda: reschedule(baseline, current, [
            Disruption("DIS_CASCADE_BREAKDOWN", DisruptionType.MACHINE_BREAKDOWN, current, "GRINDER_01", 8, "Grinder breakdown"),
            Disruption("DIS_CASCADE_ABSENCE", DisruptionType.OPERATOR_ABSENCE, current, "OP_001", 8, "Grinder operator absent"),
        ]),
    }
    for name, action in scenarios.items():
        started = time.perf_counter()
        result = action()
        result.schedule.strategy = f"REPLAN_{name.upper()}"
        errors = validate_schedule(result.schedule)
        if errors:
            raise ValueError(f"{name} rejected: {'; '.join(errors)}")
        export_schedule(result.schedule, output)
        schedule_path = output / f"schedule_{result.schedule.strategy.lower()}.csv"
        (output / f"replan_{name}.csv").write_text(schedule_path.read_text(), encoding="utf-8")
        (output / f"replan_impact_{name}.json").write_text(json.dumps({**result.impact, "runtime_seconds": time.perf_counter() - started}, indent=2, default=str) + "\n", encoding="utf-8")
        (output / f"replan_explanation_{name}.txt").write_text(result.explanation + "\n", encoding="utf-8")
        print(name, "moved", result.impact["operations_moved"], "unscheduled", len(result.schedule.unscheduled_operations), "runtime", round(time.perf_counter() - started, 3))


if __name__ == "__main__":
    main()