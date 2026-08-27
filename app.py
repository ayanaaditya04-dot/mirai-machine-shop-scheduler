"""Supervisor-facing Streamlit application.

UI orchestration only: scheduling, validation, costing, and replanning remain
in the existing src modules.
"""
from __future__ import annotations

import io
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from src.models import Disruption, DisruptionType
from src.final_memo import generate_memo
from src.replanner import reschedule
from src.scheduler.engine import STRATEGIES, export_schedule, generate_schedule, schedule_dataframe
from src.validation.schedule_validator import validate_schedule

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "outputs"
DEFENSE_TIME = datetime(2026, 9, 1, 11, 0)

LABELS = {
    "English": {"briefing": "6 AM SHIFT BRIEFING", "down": "Machine Down", "risk": "At Risk", "replan": "REPLAN", "recommendation": "Recommended Action"},
    "Kannada": {"briefing": "6 AM ಶಿಫ್ಟ್ ಮಾಹಿತಿ", "down": "ಯಂತ್ರ ಸ್ಥಗಿತ", "risk": "ಅಪಾಯ", "replan": "ಮರುಯೋಜನೆ", "recommendation": "ಶಿಫಾರಸು ಮಾಡಿದ ಕ್ರಮ"},
    "Tamil": {"briefing": "6 AM பணி விளக்கம்", "down": "இயந்திரம் செயலிழந்தது", "risk": "ஆபத்தில்", "replan": "மறுதிட்டமிடு", "recommendation": "பரிந்துரைக்கப்பட்ட நடவடிக்கை"},
}


def _read_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / name)


def _current_shift(now: datetime) -> str:
    if 6 <= now.hour < 14:
        return "MORNING"
    if 14 <= now.hour < 22:
        return "AFTERNOON"
    return "NIGHT / OVERTIME"


def _baseline(strategy: str):
    key = f"baseline_{strategy}"
    if key not in st.session_state:
        st.session_state[key] = generate_schedule(strategy, DATA_DIR)
    return st.session_state[key]


def _active_schedule():
    return st.session_state.get("replanned_schedule", _baseline(st.session_state.strategy))


def _status(row) -> str:
    if row.get("late", False):
        return "CRITICAL"
    if float(row.get("late_days", 0)) > -1:
        return "AT RISK"
    return "ON TRACK"


def _download(label: str, data: bytes, filename: str, mime: str = "text/csv"):
    st.download_button(label, data, filename, mime=mime, use_container_width=True)


def _render_briefing(labels, schedule):
    st.title(labels["briefing"])
    now = st.session_state.current_time
    st.caption(f"{now:%A, %d %b %Y %H:%M}  |  Current shift: {_current_shift(now)}")
    orders = pd.DataFrame(schedule.order_summary)
    critical = orders[orders["late"] | (orders["late_days"] > -1)]
    tier1 = orders[orders["tier"] == "TIER_1"]
    cols = st.columns(4)
    cols[0].metric("Current Shift", _current_shift(now))
    cols[1].metric("Orders at Risk", len(critical))
    cols[2].metric("Tier-1 Orders", len(tier1))
    cols[3].metric("Expected OT", f"{sum((x.end_time-x.start_time).total_seconds()/3600 for x in schedule.slots if x.shift_id.endswith('_NIGHT')):.1f} h")
    st.subheader("What is happening now?")
    machine_status = _read_csv("machines.csv")[["machine_id", "machine_type", "status"]]
    st.dataframe(machine_status, hide_index=True, use_container_width=True)
    st.subheader("What is at risk?")
    if critical.empty:
        st.success("All tracked orders are on plan.")
    else:
        display = critical[["order_id", "tier", "due_date", "promised_completion_date", "late_days"]].copy()
        st.dataframe(display, hide_index=True, use_container_width=True)
    st.subheader(labels["recommendation"])
    if not critical.empty:
        st.warning("Protect the most time-sensitive Tier-1 work first; review the disruption panel before authorizing overtime.")
    else:
        st.info("Continue the current plan and monitor the grinder and its qualified operators.")
    st.subheader("What changed from the previous plan?")
    if "replan_impact" in st.session_state:
        impact = st.session_state.replan_impact
        st.write(f"{impact['operations_moved']} operations moved; {impact['machine_changes']} machine changes; {impact['operator_changes']} operator changes.")
    else:
        st.write("No disruption has been applied in this session.")


def _render_schedule(schedule):
    st.header("Schedule")
    frame = schedule_dataframe(schedule)
    machines = st.multiselect("Machine", sorted(frame["machine_id"].unique()))
    shifts = st.multiselect("Shift", sorted(frame["shift_id"].unique()))
    orders = st.multiselect("Order", sorted(frame["order_id"].unique()))
    if machines: frame = frame[frame.machine_id.isin(machines)]
    if shifts: frame = frame[frame.shift_id.isin(shifts)]
    if orders: frame = frame[frame.order_id.isin(orders)]
    shown = frame[["machine_id", "machine_type", "shift_id", "order_id", "operation_id", "start_time", "end_time", "operator_id", "setup_time_minutes", "status"]]
    st.dataframe(shown, hide_index=True, use_container_width=True)
    _download("Download current schedule CSV", shown.to_csv(index=False).encode(), "current_schedule.csv")
    st.subheader("Machine × Shift")
    matrix = shown.pivot_table(index="machine_id", columns="shift_id", values="operation_id", aggfunc="count", fill_value=0)
    st.dataframe(matrix, use_container_width=True)


def _render_orders(schedule):
    st.header("Orders")
    orders = _read_csv("orders.csv")
    customers = _read_csv("customers.csv")[["customer_id", "name", "tier"]]
    summary = pd.DataFrame(schedule.order_summary)
    frame = orders.merge(customers, on="customer_id").merge(summary[["order_id", "promised_completion_date", "late_days", "late"]], on="order_id")
    frame["status"] = frame.apply(_status, axis=1)
    frame["risk"] = frame.apply(lambda row: "CRITICAL" if row["late"] else ("AT RISK" if row["late_days"] < 1 else "ON TRACK"), axis=1)
    tiers = st.multiselect("Customer tier", sorted(frame["tier"].unique()))
    if tiers: frame = frame[frame.tier.isin(tiers)]
    frame = frame.sort_values(["risk", "due_date"])
    st.dataframe(frame[["order_id", "name", "tier", "quantity", "due_date", "promised_completion_date", "late_days", "status", "priority", "risk"]], hide_index=True, use_container_width=True)
    _download("Download order summary CSV", frame.to_csv(index=False).encode(), "order_summary.csv")


def _make_disruptions(kind: str, values: dict) -> list[Disruption]:
    when = values["start"]
    if kind == "Machine breakdown":
        return [Disruption("UI_BREAKDOWN", DisruptionType.MACHINE_BREAKDOWN, when, values["machine"], values["duration"], f"{values['machine']} unavailable")]
    if kind == "Operator absence":
        return [Disruption("UI_ABSENCE", DisruptionType.OPERATOR_ABSENCE, when, values["operator"], values["duration"], f"{values['operator']} absent")]
    if kind == "Material delay":
        return [Disruption("UI_MATERIAL", DisruptionType.MATERIAL_DELAY, values["available"], values["order"], 0, f"Material delayed for {values['order']}")]
    return [Disruption("UI_REWORK", DisruptionType.REWORK_REQUIRED, when, values["order"], 0, f"Rework required for {values['order']}")]


def _run_replan(disruptions, rework_quantity=None):
    result = reschedule(_baseline(st.session_state.strategy), st.session_state.current_time, disruptions, DATA_DIR, rework_quantity)
    errors = validate_schedule(result.schedule, DATA_DIR)
    if errors:
        st.error("NO FEASIBLE REPLAN")
        st.code("\n".join(errors))
        return
    st.session_state.replanned_schedule = result.schedule
    st.session_state.replan_impact = result.impact
    st.session_state.replan_explanation = result.explanation
    st.success("Replan accepted and validated.")


def _render_disruptions(labels):
    st.header("Disruptions")
    machines = _read_csv("machines.csv")["machine_id"].tolist()
    operators = _read_csv("operators.csv")["operator_id"].tolist()
    orders = _read_csv("orders.csv")["order_id"].tolist()
    kind = st.selectbox("Disruption type", ["Machine breakdown", "Operator absence", "Material delay", "Rework", "Combined / cascade"])
    start_date = st.date_input("Start date", st.session_state.current_time.date())
    start_time = st.time_input("Start time", st.session_state.current_time.time())
    start = datetime.combine(start_date, start_time)
    duration = st.number_input("Duration (hours)", min_value=1.0, max_value=72.0, value=8.0, step=1.0)
    values = {"start": start, "duration": duration}
    if kind == "Machine breakdown": values["machine"] = st.selectbox("Machine", machines)
    elif kind == "Operator absence": values["operator"] = st.selectbox("Operator", operators)
    elif kind == "Material delay":
        values["order"] = st.selectbox("Order", orders)
        values["available"] = st.datetime_input("New material availability", start + timedelta(days=1))
    elif kind == "Rework":
        values["order"] = st.selectbox("Order", orders)
        values["quantity"] = st.number_input("Rework quantity", min_value=1, value=40, step=1)
    elif kind == "Combined / cascade":
        values["operator"] = st.selectbox("Absent grinder operator", operators, index=min(operators.index("OP_001"), len(operators)-1) if "OP_001" in operators else 0)
    if st.button(labels["replan"], type="primary", use_container_width=True):
        if kind == "Combined / cascade":
            _run_replan([Disruption("UI_CASCADE_BREAKDOWN", DisruptionType.MACHINE_BREAKDOWN, start, "GRINDER_01", duration, "Grinder breakdown"), Disruption("UI_CASCADE_ABSENCE", DisruptionType.OPERATOR_ABSENCE, start, values["operator"], duration, "Operator absence")])
        else:
            _run_replan(_make_disruptions(kind, values), values.get("quantity"))
    if st.button("RUN MIRAI DEFENSE SCENARIO", use_container_width=True):
        _run_replan([Disruption("UI_DEFENSE_BREAKDOWN", DisruptionType.MACHINE_BREAKDOWN, DEFENSE_TIME, "GRINDER_01", 8, "Tuesday 11 AM grinder breakdown"), Disruption("UI_DEFENSE_ABSENCE", DisruptionType.OPERATOR_ABSENCE, DEFENSE_TIME, "OP_001", 8, "Grinder-qualified operator absent")])
    if "replan_impact" in st.session_state:
        st.subheader("BEFORE ↓ DISRUPTION ↓ AFTER")
        impact = st.session_state.replan_impact
        st.json({key: value for key, value in impact.items() if key != "wasted_changeover"})
        st.text_area("Replan explanation", st.session_state.replan_explanation, height=220)
        _download("Download disruption impact", json_bytes(impact), "disruption_impact.json", "application/json")


def json_bytes(value):
    import json
    return (json.dumps(value, indent=2, default=str) + "\n").encode()


def _render_costs():
    st.header("Cost & Trade-offs")
    path = OUTPUT_DIR / "strategy_comparison.csv"
    comparison = pd.read_csv(path) if path.exists() else pd.DataFrame()
    if comparison.empty:
        st.warning("Strategy comparison is not available yet.")
        return
    st.dataframe(comparison, hide_index=True, use_container_width=True)
    _download("Download cost comparison CSV", comparison.to_csv(index=False).encode(), "strategy_comparison.csv")
    st.subheader("Recommended policy")
    best = comparison.sort_values(["Late Orders", "Total Cost (INR)"]).iloc[0]
    st.info(f"{best['Strategy']} currently offers the best delivery-first balance: {int(best['Late Orders'])} late orders at ₹{best['Total Cost (INR)']:,.2f}.")
    st.write("CHEAPEST saves operating and changeover cost but accepts more penalty exposure. MOST_ON_TIME spends more to protect delivery. MOST_ROBUST trades efficiency for slack and recovery flexibility; resilience results should guide the final policy choice.")


def _render_memo():
    st.header("Final Recommendation / Trade-off Memo")
    schedules = {strategy: _baseline(strategy) for strategy in STRATEGIES}
    memo = generate_memo(schedules["CHEAPEST"], schedules["MOST_ON_TIME"], schedules["MOST_ROBUST"])
    recommendation = next((line.removeprefix("The recommended operating policy is **").split("**", 1)[0] for line in memo.splitlines() if line.startswith("The recommended operating policy is")), "See memo")
    st.success(f"Recommended strategy: {recommendation}")
    st.markdown(memo)
    _download("Download final trade-off memo", memo.encode(), "final_tradeoff_memo.md", "text/markdown")


def main():
    st.set_page_config(page_title="Mirai Machine Shop", page_icon="⚙", layout="wide", initial_sidebar_state="expanded")
    st.markdown("""<style>h1 {font-size: 2.2rem;} .stMetric {border-left: 4px solid #0f766e; padding-left: 12px;} [data-testid='stDataFrame'] {font-size: 0.88rem;}</style>""", unsafe_allow_html=True)
    if "strategy" not in st.session_state: st.session_state.strategy = "MOST_ON_TIME"
    if "current_time" not in st.session_state: st.session_state.current_time = datetime(2026, 9, 1, 6)
    with st.sidebar:
        st.header("Mirai Shop Floor")
        st.session_state.strategy = st.selectbox("Planning policy", STRATEGIES, index=STRATEGIES.index(st.session_state.strategy))
        language = st.selectbox("Language", list(LABELS))
        st.session_state.current_time = st.datetime_input("Briefing time", st.session_state.current_time)
        st.caption("Static operational labels only. IDs and data remain unchanged.")
    labels = LABELS[language]
    schedule = _active_schedule()
    tabs = st.tabs([labels["briefing"], "Schedule", "Orders", "Disruptions", "Cost & Trade-offs", "Final Recommendation"])
    with tabs[0]: _render_briefing(labels, schedule)
    with tabs[1]: _render_schedule(schedule)
    with tabs[2]: _render_orders(schedule)
    with tabs[3]: _render_disruptions(labels)
    with tabs[4]: _render_costs()
    with tabs[5]: _render_memo()


if __name__ == "__main__":
    main()