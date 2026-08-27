"""Order and RoutingStep domain models. Pure data, no business logic."""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from .customer import Customer
from .enums import MachineType, MaterialType, Operation, OrderStatus


@dataclass
class RoutingStep:
    step_number: int
    operation: Operation
    required_machine_type: MachineType
    estimated_time_per_piece_min: float
    setup_time_min: float
    quality_check_required: bool = False
    can_run_parallel: bool = False
    batch_size: int | None = None


@dataclass
class Order:
    order_id: str
    customer: Customer
    part_name: str
    part_number: str
    quantity: int
    due_date: datetime
    routing: list[RoutingStep]
    material: MaterialType
    order_value_inr: Decimal
    priority: int = 0
    status: OrderStatus = OrderStatus.PENDING

    def __post_init__(self):
        if not self.routing:
            raise ValueError(f"Order {self.order_id} has an empty routing")
        step_numbers = [s.step_number for s in self.routing]
        if step_numbers != sorted(step_numbers):
            raise ValueError(f"Order {self.order_id} routing steps are not in sequence order")
