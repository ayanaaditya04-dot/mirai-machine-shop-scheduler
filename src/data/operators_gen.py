"""Deterministic operator generation.

Hard constraint honored here (not left to chance): exactly
`grinder_qualified_operator_count` operators (SOURCE FACT = 3) are qualified
on GRINDER. See DOMAIN_MODEL.md §1.2 and config/operators.yaml.
"""
import random
from decimal import Decimal

from src.data.seed_data import OPERATOR_NAMES, SEED
from src.models import MachineType, Operator, SkillLevel

ALL_MACHINE_TYPES = [
    MachineType.CNC_LATHE, MachineType.CNC_VMC, MachineType.CNC_HMC,
    MachineType.GRINDER, MachineType.CONV_LATHE, MachineType.RADIAL_DRILL,
    MachineType.MILLING_CONV, MachineType.CMM_INSPECTION,
]

NON_GRINDER_TYPES = [t for t in ALL_MACHINE_TYPES if t != MachineType.GRINDER]


def generate_operators(operators_cfg: dict, economics_cfg: dict) -> list[Operator]:
    rng = random.Random(SEED)

    lo, hi = operators_cfg["operator_count_range"]
    count = rng.randint(lo, hi)

    dist = operators_cfg["skill_level_distribution"]
    skill_pool = (
        [SkillLevel.MASTER] * round(dist["MASTER"] * 100)
        + [SkillLevel.SENIOR] * round(dist["SENIOR"] * 100)
        + [SkillLevel.JUNIOR] * round(dist["JUNIOR"] * 100)
    )

    wage_cfg = economics_cfg["operator_wages"]
    overtime_willing_pct = operators_cfg["overtime_willing_pct"]
    grinder_count = operators_cfg["grinder_qualified_operator_count"]
    q_lo, q_hi = operators_cfg["qualifications_per_operator_range"]
    master_preferred = set(operators_cfg["master_preferred_machine_types"])

    names = OPERATOR_NAMES[:count]
    operators: list[Operator] = []

    # Step 1: assign skill levels deterministically
    skills = [rng.choice(skill_pool) for _ in range(count)]

    # Step 2: pick exactly `grinder_count` operators to be grinder-qualified.
    # Prefer MASTER/SENIOR for the bottleneck machine (plausible shop practice).
    candidate_order = sorted(
        range(count),
        key=lambda i: (skills[i] != SkillLevel.MASTER, skills[i] != SkillLevel.SENIOR, i),
    )
    grinder_operator_indices = set(candidate_order[:grinder_count])

    for i in range(count):
        op_id = f"OP_{i + 1:03d}"
        name = names[i]
        skill = skills[i]
        wage = Decimal(str(wage_cfg[skill.value]["hourly_rate_inr"]))
        overtime_willing = rng.random() < overtime_willing_pct

        n_quals = rng.randint(q_lo, q_hi)
        quals = set()
        if i in grinder_operator_indices:
            quals.add(MachineType.GRINDER)
            n_quals -= 1

        pool = list(NON_GRINDER_TYPES)
        if skill in (SkillLevel.MASTER, SkillLevel.SENIOR):
            # weight toward master-preferred types by duplicating them in the sample pool
            pool = pool + [t for t in master_preferred if t != MachineType.GRINDER] * 2

        n_quals = max(0, min(n_quals, len(NON_GRINDER_TYPES)))
        extra = set()
        while len(extra) < n_quals:
            extra.add(rng.choice(pool))
        quals |= extra

        operators.append(
            Operator(
                operator_id=op_id,
                name=name,
                qualified_machines=frozenset(quals),
                skill_level=skill,
                hourly_rate_inr=wage,
                overtime_willing=overtime_willing,
            )
        )

    return operators
