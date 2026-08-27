"""Shift domain model. Pure data, no business logic."""
from dataclasses import dataclass
from datetime import date, datetime

from .enums import ShiftType


@dataclass
class Shift:
    shift_type: ShiftType
    date: date
    start_time: datetime
    end_time: datetime
    available_hours: float
    is_regular_capacity: bool   # False for NIGHT — overtime-only, see DOMAIN_MODEL.md
    premium_multiplier: float = 1.0

    @property
    def shift_id(self) -> str:
        return f"{self.date.isoformat()}_{self.shift_type.value}"
