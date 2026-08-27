"""Customer generation. The customer list itself is hand-authored in
config/customers_orders.yaml (not randomly generated) because it encodes a
SOURCE FACT that must hold exactly: one TIER_1 customer at ~60% revenue share,
JIT. Randomly sampling that fact away would be a bug, not realism.
"""
from src.models import Customer, CustomerTier


def generate_customers(customers_orders_cfg: dict) -> list[Customer]:
    customers = []
    total_share = 0.0
    for i, c in enumerate(customers_orders_cfg["customers"]):
        total_share += c["revenue_share"]
        customers.append(
            Customer(
                customer_id=f"CUST_{i + 1:03d}",
                name=c["name"],
                tier=CustomerTier(c["tier"]),
                revenue_share=c["revenue_share"],
                just_in_time=c["just_in_time"],
                relationship_years=c["relationship_years"],
            )
        )
    assert abs(total_share - 1.0) < 1e-6, (
        f"customers_orders.yaml revenue_share values sum to {total_share}, must sum to 1.0"
    )
    return customers
