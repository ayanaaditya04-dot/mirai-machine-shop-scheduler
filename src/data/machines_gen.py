"""Load the fixed 14-machine roster from config/machines.yaml into Machine objects.

The roster itself is not randomly generated (it's a SOURCE FACT: "14 machines"),
but planned maintenance windows within the 14-day horizon ARE deterministically
generated here (seed=42), per DOMAIN_MODEL.md A-12.
"""
import random
from datetime import datetime, timedelta
from decimal import Decimal

from src.data.seed_data import SEED
from src.models import Machine, MaintenanceWindow, MachineType, Operation


def generate_machines(machines_cfg: dict, horizon_start: datetime) -> list[Machine]:
    rng = random.Random(SEED)
    mw_cfg = machines_cfg["planned_maintenance"]
    dur_lo, dur_hi = mw_cfg["duration_hours_range"]
    windows_per_machine = mw_cfg["windows_per_machine"]

    machines = []
    for m in machines_cfg["machines"]:
        capabilities = frozenset(Operation(op) for op in m["capabilities"])

        maintenance_windows = []
        for _ in range(windows_per_machine):
            # place the window somewhere in days 1-13 of the 14-day horizon
            day_offset = rng.randint(1, 12)
            hour_offset = rng.randint(6, 20)
            start = horizon_start + timedelta(days=day_offset, hours=hour_offset)
            duration = rng.randint(dur_lo, dur_hi)
            end = start + timedelta(hours=duration)
            maintenance_windows.append(MaintenanceWindow(start=start, end=end))

        machines.append(
            Machine(
                machine_id=m["machine_id"],
                name=m["name"],
                machine_type=MachineType(m["machine_type"]),
                hourly_rate_inr=Decimal(str(m["hourly_rate_inr"])),
                capabilities=capabilities,
                mtbf_hours=float(m["mtbf_hours"]),
                mttr_hours=float(m["mttr_hours"]),
                planned_maintenance_windows=maintenance_windows,
            )
        )
    return machines
