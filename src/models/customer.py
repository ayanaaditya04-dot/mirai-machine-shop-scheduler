"""Customer domain model. Pure data, no business logic."""
from dataclasses import dataclass

from .enums import CustomerTier

# Late penalty % per day by tier (SOURCE FACT-adjacent values from ECONOMICS.md §4)
TIER_PENALTY_PCT = {
    CustomerTier.TIER_1: 2.0,
    CustomerTier.TIER_2: 1.0,
    CustomerTier.TIER_3: 0.5,
}

TIER_PENALTY_CAP_PCT = {
    CustomerTier.TIER_1: 10.0,
    CustomerTier.TIER_2: 8.0,
    CustomerTier.TIER_3: 5.0,
}


@dataclass
class Customer:
    customer_id: str
    name: str
    tier: CustomerTier
    revenue_share: float          # fraction of total order-book value this customer represents
    just_in_time: bool
    relationship_years: int

    @property
    def late_penalty_pct(self) -> float:
        return TIER_PENALTY_PCT[self.tier]

    @property
    def late_penalty_cap_pct(self) -> float:
        return TIER_PENALTY_CAP_PCT[self.tier]
