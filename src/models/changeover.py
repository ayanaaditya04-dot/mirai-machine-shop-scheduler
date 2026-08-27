"""Changeover domain model. Pure data, no business logic.

Implemented as rule-based categories (MINOR/MEDIUM/MAJOR), not a full
machine_type x material x material x operation x operation matrix — see
config/changeover_matrix.yaml for the rationale (Phase-1 audit finding:
the full matrix is unnecessary complexity for this assignment's scope).
"""
from dataclasses import dataclass
from decimal import Decimal

from .enums import ChangeoverCategory, MachineType, MaterialType, Operation


@dataclass
class ChangeoverEntry:
    machine_type: MachineType
    from_material: MaterialType
    to_material: MaterialType
    from_operation: Operation
    to_operation: Operation
    category: ChangeoverCategory
    changeover_time_min: float
    changeover_cost_inr: Decimal
