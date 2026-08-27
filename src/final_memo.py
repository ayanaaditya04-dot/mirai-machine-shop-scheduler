"""Phase 6 final trade-off memo generation."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from src.data.load import load_economics_config


def _metrics(schedule) -> dict:
    slots = schedule.slots
    machine_hours: dict[str, float] = {}
    for slot in slots:
        machine_hours[slot.machine_id] = machine_hours.get(slot.machine_id, 0.0) + (slot.end_time - slot.start_time).total_seconds() / 3600 + slot.setup_time_minutes / 60
    slack = [(datetime.fromisoformat(row["due_date"]) - datetime.fromisoformat(row["promised_completion_date"])).total_seconds() / 86400 for row in schedule.order_summary if row["promised_completion_date"]]
    late = [row for row in schedule.order_summary if row["late"]]
    overtime_hours = sum((slot.end_time - slot.start_time).total_seconds() / 3600 for slot in slots if slot.shift_id.endswith("_NIGHT"))
    return {
        "Total cost": schedule.cost_summary["total_cost"],
        "Machine cost": schedule.cost_summary["machine_cost"],
        "Operator cost": schedule.cost_summary["operator_cost"],
        "Overtime cost": schedule.cost_summary["overtime_cost"],
        "Changeover cost": schedule.cost_summary["changeover_cost"],
        "Penalty cost": schedule.cost_summary["penalty_cost"],
        "Overtime hours": overtime_hours,
        "Late orders": len(late),
        "Total tardiness": sum(float(row["late_days"]) for row in late),
        "Maximum lateness": max((float(row["late_days"]) for row in late), default=0.0),
        "On-time orders": sum(not row["late"] for row in schedule.order_summary),
        "Average slack": sum(slack) / len(slack) if slack else 0.0,
        "Machine utilization": sum(machine_hours.values()) / (14 * 210) * 100,
        "Grinder utilization": machine_hours.get("GRINDER_01", 0.0) / 210 * 100,
        "Unscheduled operations": len(schedule.unscheduled_operations),
    }


def _recommend(metrics: dict[str, dict], weights: dict[str, float]) -> tuple[str, dict[str, float]]:
    lower_is_better = {"total_cost", "late_orders", "tardiness", "overtime", "changeover"}
    values = {
        "total_cost": {name: data["Total cost"] for name, data in metrics.items()},
        "late_orders": {name: data["Late orders"] for name, data in metrics.items()},
        "tardiness": {name: data["Total tardiness"] for name, data in metrics.items()},
        "overtime": {name: data["Overtime hours"] for name, data in metrics.items()},
        "changeover": {name: data["Changeover cost"] for name, data in metrics.items()},
        "slack_resilience": {name: data["Average slack"] for name, data in metrics.items()},
    }
    normalized = {}
    for factor, factor_values in values.items():
        lo, hi = min(factor_values.values()), max(factor_values.values())
        span = hi - lo
        normalized[factor] = {name: (0.0 if span == 0 else ((value - lo) / span if factor in lower_is_better else (hi - value) / span)) for name, value in factor_values.items()}
    scores = {name: round(sum(weights[factor] * normalized[factor][name] for factor in weights), 6) for name in metrics}
    return min(scores, key=scores.get), scores


def generate_memo(schedule_cheapest, schedule_ontime, schedule_robust) -> str:
    schedules = {"CHEAPEST": schedule_cheapest, "MOST_ON_TIME": schedule_ontime, "MOST_ROBUST": schedule_robust}
    actual = {name: _metrics(schedule) for name, schedule in schedules.items()}
    config = load_economics_config()
    weights = config["recommendation_weights"]
    recommended, scores = _recommend(actual, weights)
    table = pd.DataFrame.from_dict(actual, orient="index")
    display_columns = ["Total cost", "Machine cost", "Operator cost", "Overtime cost", "Changeover cost", "Penalty cost", "Overtime hours", "Late orders", "Total tardiness", "Maximum lateness", "On-time orders", "Average slack", "Machine utilization", "Grinder utilization", "Unscheduled operations"]
    table = table[display_columns]
    table.index.name = "Strategy"
    table = table.reset_index()
    table = table.round(3)
    markdown_table = _markdown_table(table)
    weight_lines = "\n".join(f"- `{factor}`: {weight:.0%}" for factor, weight in weights.items())
    score_lines = "\n".join(f"- **{name}**: `{score:.6f}`" for name, score in sorted(scores.items(), key=lambda item: item[1]))
    reasons = {
        "CHEAPEST": "It has the strongest weighted result because its cost and operating-friction savings outweigh its delivery exposure under the configured priorities.",
        "MOST_ON_TIME": "It has the strongest weighted result because it protects delivery while also performing competitively on total cost in this dataset.",
        "MOST_ROBUST": "It has the strongest weighted result because its slack and resilience profile outweigh its additional cost and operating exposure under the configured priorities.",
    }
    return f"""# Final Trade-off Memo

## Executive Summary

The recommended operating policy is **{recommended}**. This recommendation is calculated from the actual generated schedules, their cost breakdowns, delivery results, operating hours, and slack. No strategy is forced to win.

## Strategy Comparison

{markdown_table}

## Weighted Recommendation

The configured recommendation weights are:

{weight_lines}

Scores are normalized across the three actual schedules. Lower is better for cost, late orders, tardiness, overtime, and changeover. Higher average slack is better for resilience.

{score_lines}

## Strengths and Weaknesses

### CHEAPEST

**Strengths:** Focuses on direct operating cost, overtime cost, changeovers, and delivery penalties. It is useful when cash cost is the owner's main concern.

**Weaknesses:** It accepts more delivery exposure when protecting every due date costs more than the expected penalty.

### MOST_ON_TIME

**Strengths:** Gives delivery urgency and customer commitments strong priority. It is useful when late shipments threaten customer relationships.

**Weaknesses:** It may spend more on overtime, alternative resources, or changeovers to protect dates.

### MOST_ROBUST

**Strengths:** Values slack, reliability, bottleneck pressure, operator scarcity, and recovery flexibility.

**Weaknesses:** It can sacrifice immediate cost or delivery performance to preserve operating room for disruptions.

## Why This Strategy Was Recommended

{reasons[recommended]}

For a factory owner or supervisor, the practical reading is: choose **{recommended}** for this planning horizon because it gives the best balance of the business outcomes represented by the configured weights. Re-evaluate the choice when order mix, due dates, costs, or disruption exposure changes.

## Limitations

- This recommendation depends on the current generated dataset.
- It depends on the configured economic and business weights.
- The score is a transparent decision aid, not a guarantee of future schedule performance.
- Robustness is represented by available schedule metrics; future disruption scenarios may change the preferred policy.
"""


def _markdown_table(table: pd.DataFrame) -> str:
    headers = list(table.columns)
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in table.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def write_final_memo(schedules: dict, output_path: str | Path = "outputs/final_tradeoff_memo.md") -> Path:
    content = generate_memo(schedules["CHEAPEST"], schedules["MOST_ON_TIME"], schedules["MOST_ROBUST"])
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path