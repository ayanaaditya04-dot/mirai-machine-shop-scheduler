"""Operator domain model. Pure data, no business logic."""
from dataclasses import dataclass
from decimal import Decimal

from .enums import MachineType, SkillLevel


@dataclass
class Operator:
    operator_id: str
    name: str
    qualified_machines: frozenset[MachineType]
    skill_level: SkillLevel
    hourly_rate_inr: Decimal
    overtime_willing: bool = False

    def is_qualified_for(self, machine_type: MachineType) -> bool:
        return machine_type in self.qualified_machines
