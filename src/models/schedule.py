"""Baseline schedule output objects used by Phase 2."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ScheduleSlot:
    slot_id: str
    machine_id: str
    machine_type: str
    operator_id: str
    shift_id: str
    order_id: str
    operation_id: str
    sequence: float
    setup_family: str
    setup_time_minutes: float
    start_time: datetime
    end_time: datetime
    status: str = "PLANNED"
    machine_cost: float = 0.0
    operator_cost: float = 0.0
    overtime_cost: float = 0.0
    changeover_cost: float = 0.0
    explanation: str = ""
    decision_log: dict[str, Any] = field(default_factory=dict)


@dataclass
class Schedule:
    strategy: str
    slots: list[ScheduleSlot]
    order_summary: list[dict[str, Any]]
    cost_summary: dict[str, float]
    unscheduled_operations: list[str] = field(default_factory=list)

    @property
    def completion_rate(self) -> float:
        total = len(self.order_summary)
        return sum(row["promised_completion_date"] is not None for row in self.order_summary) / total if total else 1.0