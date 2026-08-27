"""Cost domain model. Pure data, no business logic."""
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class CostBreakdown:
    machine_cost_inr: Decimal
    operator_cost_inr: Decimal
    overtime_cost_inr: Decimal = Decimal("0")
    changeover_cost_inr: Decimal = Decimal("0")
    penalty_cost_inr: Decimal = Decimal("0")
    notes: str = ""

    @property
    def total_cost_inr(self) -> Decimal:
        return (
            self.machine_cost_inr
            + self.operator_cost_inr
            + self.overtime_cost_inr
            + self.changeover_cost_inr
            + self.penalty_cost_inr
        )
