from datetime import datetime, timedelta

from src.data_generator import generate_dataset
from src.scheduler.engine import STRATEGIES, build_jobs, generate_schedule
from src.validation.schedule_validator import validate_schedule


def test_build_jobs_and_precedence(tmp_path):
    generate_dataset(tmp_path)
    jobs = build_jobs(tmp_path)
    assert len(jobs) == 25
    assert all(3 <= len(job.operations) <= 6 for job in jobs)
    schedule = generate_schedule("MOST_ON_TIME", tmp_path)
    assert validate_schedule(schedule, tmp_path) == []
    for job in jobs:
        slots = sorted((slot for slot in schedule.slots if slot.order_id == job.order_id), key=lambda slot: slot.sequence)
        assert all(left.end_time <= right.start_time for left, right in zip(slots, slots[1:]))


def test_all_strategies_produce_valid_complete_schedules(tmp_path):
    generate_dataset(tmp_path)
    for strategy in STRATEGIES:
        schedule = generate_schedule(strategy, tmp_path)
        assert not schedule.unscheduled_operations
        assert validate_schedule(schedule, tmp_path) == []
        assert schedule.completion_rate == 1.0
        assert schedule.cost_summary["total_cost"] > 0


def test_promised_completion_is_actual_final_operation(tmp_path):
    generate_dataset(tmp_path)
    schedule = generate_schedule("CHEAPEST", tmp_path)
    for summary in schedule.order_summary:
        final = max(slot.end_time for slot in schedule.slots if slot.order_id == summary["order_id"])
        assert summary["promised_completion_date"] == final.isoformat()


def test_sequence_aware_changeover_changes_with_previous_family(tmp_path):
    generate_dataset(tmp_path)
    first = generate_schedule("CHEAPEST", tmp_path)
    assert len({slot.setup_time_minutes for slot in first.slots}) > 1
