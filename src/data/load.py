"""Load config/*.yaml into plain Python dicts. No business logic here."""
from pathlib import Path
import yaml

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def _load(filename: str) -> dict:
    path = CONFIG_DIR / filename
    with open(path, "r") as f:
        return yaml.safe_load(f)


def load_machines_config() -> dict:
    return _load("machines.yaml")


def load_shifts_config() -> dict:
    return _load("shifts.yaml")


def load_economics_config() -> dict:
    return _load("economics.yaml")


def load_operators_config() -> dict:
    return _load("operators.yaml")


def load_customers_orders_config() -> dict:
    return _load("customers_orders.yaml")


def load_changeover_config() -> dict:
    return _load("changeover_matrix.yaml")


def load_disruption_scenarios_config() -> dict:
    return _load("disruption_scenarios.yaml")


def load_assumptions_config() -> dict:
    return _load("assumptions.yaml")


def load_all() -> dict:
    return {
        "machines": load_machines_config(),
        "shifts": load_shifts_config(),
        "economics": load_economics_config(),
        "operators": load_operators_config(),
        "customers_orders": load_customers_orders_config(),
        "changeover": load_changeover_config(),
        "disruption_scenarios": load_disruption_scenarios_config(),
        "assumptions": load_assumptions_config(),
    }
