"""Generate and validate all Phase 2 baseline schedules."""
from pathlib import Path

import pandas as pd

from src.scheduler.engine import STRATEGIES, export_schedule, generate_schedule
from src.validation.schedule_validator import validate_schedule


def run_all(data_dir: str | Path = "data", output_dir: str | Path = "outputs") -> pd.DataFrame:
    rows = []
    schedules = {}
    for strategy in STRATEGIES:
        schedule = generate_schedule(strategy, data_dir)
        errors = validate_schedule(schedule, data_dir)
        if errors:
            raise ValueError(f"{strategy} rejected: {'; '.join(errors)}")
        export_schedule(schedule, output_dir)
        schedules[strategy] = schedule
        machine_hours = {machine_id: 0.0 for machine_id in {slot.machine_id for slot in schedule.slots}}
        operator_hours = {}
        for slot in schedule.slots:
            occupied_hours = (slot.end_time - slot.start_time).total_seconds() / 3600 + slot.setup_time_minutes / 60
            machine_hours[slot.machine_id] += occupied_hours
            operator_hours[slot.operator_id] = operator_hours.get(slot.operator_id, 0.0) + occupied_hours
        operation_hours = sum(machine_hours.values())
        grinder_hours = machine_hours.get("GRINDER_01", 0.0)
        late = [row for row in schedule.order_summary if row["late"]]
        overtime_hours = sum((slot.end_time - slot.start_time).total_seconds() / 3600 for slot in schedule.slots if slot.shift_id.endswith("_NIGHT"))
        slack = [(pd.Timestamp(row["due_date"]) - pd.Timestamp(row["promised_completion_date"])).total_seconds() / 86400 for row in schedule.order_summary if row["promised_completion_date"]]
        rows.append({
            "Strategy": strategy,
            "Total Cost (INR)": schedule.cost_summary["total_cost"],
            "Machine Cost (INR)": schedule.cost_summary["machine_cost"],
            "Operator Cost (INR)": schedule.cost_summary["operator_cost"],
            "Overtime Cost (INR)": schedule.cost_summary["overtime_cost"],
            "Changeover Cost (INR)": schedule.cost_summary["changeover_cost"],
            "Penalty Cost (INR)": schedule.cost_summary["penalty_cost"],
            "OT Hours": round(overtime_hours, 3),
            "Late Orders": len(late),
            "Total Tardiness (days)": round(sum(row["late_days"] for row in late), 3),
            "Maximum Lateness (days)": round(max((row["late_days"] for row in late), default=0), 3),
            "On-Time Orders": sum(not row["late"] for row in schedule.order_summary),
            "Average Slack (days)": round(sum(slack) / len(slack), 3),
            "Minimum Slack (days)": round(min(slack), 3),
            "Average Machine Utilization (%)": round(sum(value / 210 * 100 for value in machine_hours.values()) / 14, 2),
            "Maximum Machine Utilization (%)": round(max(machine_hours.values(), default=0) / 210 * 100, 2),
            "Grinder Utilization (%)": round(grinder_hours / 210 * 100, 2),
            "Grinder-Operator Utilization (%)": round(sum((slot.end_time - slot.start_time).total_seconds() / 3600 + slot.setup_time_minutes / 60 for slot in schedule.slots if slot.machine_type == "GRINDER") / (3 * 210) * 100, 2),
            "Bottleneck Utilization (%)": round(max(machine_hours.values(), default=0) / 210 * 100, 2),
            "Unscheduled Operations": len(schedule.unscheduled_operations),
            "Completion Rate (%)": round(schedule.completion_rate * 100, 2),
        })
    report = pd.DataFrame(rows)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    report.to_csv(output / "comparison_report.csv", index=False)
    report.to_csv(output / "strategy_comparison.csv", index=False)
    _write_tradeoff_report(report, schedules, output)
    _write_strategy_aliases(output)
    return report


def _write_strategy_aliases(output: Path) -> None:
    aliases = {"most_on_time": "ontime", "most_robust": "robust"}
    for source, target in aliases.items():
        for prefix in ("schedule", "order_summary", "cost_summary"):
            source_path = output / f"{prefix}_{source}.{'json' if prefix == 'cost_summary' else 'csv'}"
            target_path = output / f"{prefix}_{target}.{'json' if prefix == 'cost_summary' else 'csv'}"
            if source_path.exists():
                target_path.write_bytes(source_path.read_bytes())


def _write_tradeoff_report(report: pd.DataFrame, schedules: dict, output: Path) -> None:
    cheapest = {slot.operation_id: slot for slot in schedules["CHEAPEST"].slots}
    differences = []
    for operation_id, base in cheapest.items():
        choices = [schedules[name].slots for name in ("MOST_ON_TIME", "MOST_ROBUST")]
        alternatives = [next((slot for slot in slots if slot.operation_id == operation_id), None) for slots in choices]
        if any(slot and (slot.machine_id, slot.operator_id, slot.shift_id) != (base.machine_id, base.operator_id, base.shift_id) for slot in alternatives):
            differences.append((operation_id, base, alternatives))
    lines = ["STRATEGY TRADE-OFF REPORT", "", "The same dataset and feasibility validator were used for all strategies.", ""]
    for row in report.to_dict("records"):
        strategy = row["Strategy"]
        lines.append(f"{strategy}: total cost ₹{row['Total Cost (INR)']:.2f}; {row['Late Orders']} late orders; {row['OT Hours']:.3f} OT hours; average slack {row['Average Slack (days)']:.3f} days; grinder utilization {row['Grinder Utilization (%)']:.2f}%.")
    lines += ["", "Policy explanations:", "CHEAPEST: minimizes operating, overtime, changeover, and penalty exposure.", "MOST_ON_TIME: accepts additional cost/changeovers when that protects due-date and Tier-1 commitments.", "MOST_ROBUST: values slack, reliability, and recovery flexibility around constrained resources.", "", "Top differing operation decisions:"]
    for operation_id, base, alternatives in differences[:10]:
        choices = [base] + alternatives
        lines.append(f"{operation_id}: " + " | ".join(f"{slot.machine_id}/{slot.operator_id}/{slot.shift_id}" if slot else "unscheduled" for slot in choices))
    (output / "strategy_tradeoff_report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    print(run_all().to_string(index=False))