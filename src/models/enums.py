"""Shared enumerations for the domain model.

See DOMAIN_MODEL.md for the source-of-truth definitions and classification
(SOURCE FACT / ASSUMPTION / DERIVED DECISION) of each value.
"""
from enum import Enum


class MachineType(str, Enum):
    CNC_LATHE = "CNC_LATHE"
    CNC_VMC = "CNC_VMC"
    CNC_HMC = "CNC_HMC"
    GRINDER = "GRINDER"                # singular — the shop's one grinder (SOURCE FACT)
    CONV_LATHE = "CONV_LATHE"
    RADIAL_DRILL = "RADIAL_DRILL"
    MILLING_CONV = "MILLING_CONV"
    CMM_INSPECTION = "CMM_INSPECTION"


class MachineStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    IN_USE = "IN_USE"
    UNDER_MAINTENANCE = "UNDER_MAINTENANCE"
    BROKEN_DOWN = "BROKEN_DOWN"


class Operation(str, Enum):
    TURNING = "TURNING"
    FACING = "FACING"
    THREADING = "THREADING"
    BORING = "BORING"
    MILLING = "MILLING"
    DRILLING = "DRILLING"
    TAPPING = "TAPPING"
    REAMING = "REAMING"
    SURFACE_GRINDING = "SURFACE_GRINDING"
    CYLINDRICAL_GRINDING = "CYLINDRICAL_GRINDING"
    INSPECTION = "INSPECTION"


class MaterialType(str, Enum):
    MILD_STEEL = "MILD_STEEL"
    EN8 = "EN8"
    EN24 = "EN24"
    EN31 = "EN31"
    STAINLESS_STEEL_304 = "STAINLESS_STEEL_304"
    STAINLESS_STEEL_316 = "STAINLESS_STEEL_316"
    CAST_IRON = "CAST_IRON"
    ALUMINIUM_6061 = "ALUMINIUM_6061"
    BRASS = "BRASS"
    BRONZE = "BRONZE"


class SkillLevel(str, Enum):
    JUNIOR = "JUNIOR"
    SENIOR = "SENIOR"
    MASTER = "MASTER"


class ShiftType(str, Enum):
    MORNING = "MORNING"
    AFTERNOON = "AFTERNOON"
    NIGHT = "NIGHT"      # overtime-only — see DOMAIN_MODEL.md §ShiftType


class CustomerTier(str, Enum):
    TIER_1 = "TIER_1"
    TIER_2 = "TIER_2"
    TIER_3 = "TIER_3"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    DELAYED = "DELAYED"


class ChangeoverCategory(str, Enum):
    MINOR = "MINOR"
    MEDIUM = "MEDIUM"
    MAJOR = "MAJOR"


class DisruptionType(str, Enum):
    MACHINE_BREAKDOWN = "MACHINE_BREAKDOWN"
    OPERATOR_ABSENCE = "OPERATOR_ABSENCE"
    MATERIAL_DELAY = "MATERIAL_DELAY"
    REWORK_REQUIRED = "REWORK_REQUIRED"
    POWER_CUT = "POWER_CUT"          # added — was missing (Phase-1 audit finding)


class SlotStatus(str, Enum):
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    RESCHEDULED = "RESCHEDULED"
