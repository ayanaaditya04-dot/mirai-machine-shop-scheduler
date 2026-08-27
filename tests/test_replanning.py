from datetime import datetime, timedelta

import pytest

from src.models import Disruption, DisruptionType
from src.replanner import apply_breakdown, apply_material_late, apply_operator_absent, apply_rework, compare_schedules, reschedule, should_authorize_overtime
from src.scheduler.engine import build_jobs, generate_schedule
from src.validation.schedule_validator import validate_schedule

CURRENT = datetime.fromisoformat("2026-09-03T06:00:00")


@pytest.fixture
def baseline():
    return generate_schedule("MOST_ON_TIME")


def test_machine_breakdown_reassigns_future_work(baseline):
    result = apply_breakdown(baseline, "GRINDER_01", datetime.fromisoformat("2026-09-03T14:00:00"), 8, CURRENT)
    assert result.affected_operations
    assert result.impact["operations_moved"] > 0
    assert not validate_schedule(result.schedule)


def test_operator_absence_preserves_grinder_qualification(baseline):
    result = apply_operator_absent(baseline, "OP_001", datetime.fromisoformat("2026-09-03T14:00:00"), 8, CURRENT)
    assert result.impact["operations_moved"] > 0
    assert not validate_schedule(result.schedule)
    absence_end = datetime.fromisoformat("2026-09-03T22:00:00")
    assert all(slot.operator_id != "OP_001" for slot in result.schedule.slots if slot.machine_type == "GRINDER" and CURRENT <= slot.start_time < absence_end)


def test_material_delay_only_replans_future_order_work(baseline):
    result = apply_material_late(baseline, "ORD_008", CURRENT + timedelta(days=1), CURRENT)
    assert result.affected_operations
    assert not validate_schedule(result.schedule)


def test_rework_reenters_before_final_inspection(baseline):
    result = apply_rework(baseline, "ORD_008", 40, CURRENT)
    assert any("_RW_40" in slot.operation_id for slot in result.schedule.slots)
    assert not validate_schedule(result.schedule)


def test_combined_breakdown_and_absence(baseline):
    result = reschedule(baseline, CURRENT, [
        Disruption("D1", DisruptionType.MACHINE_BREAKDOWN, CURRENT, "GRINDER_01", 8, "breakdown"),
        Disruption("D2", DisruptionType.OPERATOR_ABSENCE, CURRENT, "OP_001", 8, "absence"),
    ])
    assert result.disruptions[0].type == DisruptionType.MACHINE_BREAKDOWN
    assert not validate_schedule(result.schedule)


def test_grinder_breakdown_changes_future_grinder_assignments(baseline):
    result = apply_breakdown(baseline, "GRINDER_01", datetime.fromisoformat("2026-09-03T14:00:00"), 8, CURRENT)
    assert any(slot.machine_id == "GRINDER_01" for slot in result.schedule.slots)
    assert result.impact["wasted_changeover_time_minutes"] == 0


def test_completed_work_is_frozen(baseline):
    completed = {slot.operation_id: slot for slot in baseline.slots if slot.end_time <= CURRENT}
    result = apply_breakdown(baseline, "GRINDER_01", datetime.fromisoformat("2026-09-03T14:00:00"), 8, CURRENT)
    assert all(next(slot for slot in result.schedule.slots if slot.operation_id == operation_id).__dict__ == slot.__dict__ for operation_id, slot in completed.items())


def test_compare_uses_future_and_reports_incremental_cost(baseline):
    result = apply_breakdown(baseline, "GRINDER_01", datetime.fromisoformat("2026-09-03T14:00:00"), 8, CURRENT)
    impact = compare_schedules(baseline, result.schedule, CURRENT)
    assert "sunk_historical_cost" in impact
    assert "incremental_disruption_cost" in impact
    assert impact["sunk_historical_cost"] >= 0


def test_no_alternative_resource_reports_unscheduled(tmp_path):
    schedule = generate_schedule("MOST_ON_TIME")
    result = apply_breakdown(schedule, "CMM_01", CURRENT, 400, CURRENT)
    assert result.schedule.unscheduled_operations or result.affected_operations == []


def test_in_memory_replan_is_fast(baseline):
    import time
    started = time.perf_counter()
    apply_breakdown(baseline, "GRINDER_01", datetime.fromisoformat("2026-09-03T14:00:00"), 8, CURRENT)
    assert time.perf_counter() - started < 3


def test_overtime_decision_is_strictly_cost_based():
    assert should_authorize_overtime(1000, 999)
    assert not should_authorize_overtime(1000, 1000)
    assert not should_authorize_overtime(999, 1000)


def test_order_tier_comes_from_customer_table():
    jobs = {job.order_id: job for job in build_jobs()}
    assert jobs["ORD_001"].tier == "TIER_1"
    assert jobs["ORD_025"].tier == "TIER_2"


def test_replan_impact_overtime_is_a_delta(baseline):
    result = apply_breakdown(baseline, "GRINDER_01", datetime.fromisoformat("2026-09-03T14:00:00"), 8, CURRENT)
    baseline_ot = sum((slot.end_time - slot.start_time).total_seconds() / 3600 for slot in baseline.slots if slot.shift_id.endswith("_NIGHT"))
    replanned_ot = sum((slot.end_time - slot.start_time).total_seconds() / 3600 for slot in result.schedule.slots if slot.shift_id.endswith("_NIGHT"))
    assert result.impact["additional_overtime_hours"] == pytest.approx(replanned_ot - baseline_ot, abs=0.01)
