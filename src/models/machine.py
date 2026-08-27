"""Machine domain model. Pure data, no business logic."""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from .enums import MachineType, MachineStatus, Operation


@dataclass
class MaintenanceWindow:
    start: datetime
    end: datetime


@dataclass
class Machine:
    machine_id: str
    name: str
    machine_type: MachineType
    hourly_rate_inr: Decimal
    capabilities: frozenset[Operation]
    mtbf_hours: float
    mttr_hours: float
    status: MachineStatus = MachineStatus.AVAILABLE
    max_shifts_per_day: int = 2  # regular capacity; NIGHT is overtime-only, not counted here
    planned_maintenance_windows: list[MaintenanceWindow] = field(default_factory=list)

    def can_perform(self, operation: Operation) -> bool:
        return operation in self.capabilities
