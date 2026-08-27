"""Disruption domain model. Pure data, no business logic.

Includes POWER_CUT, which was missing from the original design draft
(Phase-1 audit finding) despite being an explicit item in the assignment
brief's "reality attacks daily" list.
"""
from dataclasses import dataclass

from .enums import DisruptionType


@dataclass
class Disruption:
    disruption_id: str
    type: DisruptionType
    timestamp: object  # datetime; kept loose here to avoid a circular import at this layer
    affected_entity_id: str
    duration_hours: float
    description: str
    resolution: str = ""
    # POWER_CUT-only fields (see ECONOMICS.md §3B)
    generator_available: bool | None = None
    generator_cost_multiplier: float | None = None
