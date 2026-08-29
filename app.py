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
    "English": {
        "briefing": "6 AM SHIFT BRIEFING",
        "down": "Machine Down",
        "risk": "At Risk",
        "replan": "REPLAN",
        "recommendation": "Recommended Action",
        "how_to_use_title": "How to use this dashboard",
        "how_to_use_steps": "Use this dashboard in four steps:\n\n1. **Review the current schedule** to see which machine, operator and shift are assigned to each operation.\n2. **Check Orders** to see promised completion dates, due dates and lateness.\n3. **If something goes wrong**, open Disruptions, select the real-world disruption and enter its details. Click Replan to generate a new feasible plan while preserving completed/in-progress work.\n4. **Use Cost Analysis** to compare Cheapest, Most On-Time and Most Robust planning strategies.",
        "how_to_use_constraints": "**Important**: The system does not silently ignore constraints. Machine capability, operator qualification, material availability, maintenance, breakdowns, routing precedence and shift/overtime rules are considered during scheduling and replanning.",
        "schedule_intro": "**Current Schedule**\n\nThis table shows where each production operation is planned to run, who will operate the machine, and when the work is expected to happen.",
        "schedule_how_to_read": "**How to read this schedule**\n\n- **Machine ID** = the physical machine assigned to the operation.\n- **Machine Type** = the capability/family of the machine.\n- **Operator ID** = the qualified operator assigned to perform the operation.\n- **Shift ID** = the production shift in which the operation is scheduled.\n- **Order ID** = the customer order being processed.\n- **Operation ID** = unique identifier for the operation.\n- **Setup Time** = changeover/setup time required before production.\n- **Start Time** = exact planned production start.\n- **End Time** = exact planned production completion.\n- **Status** = current scheduling state.\n\n**Operations are scheduled in sequence.** A later operation cannot begin before its predecessor is completed.",
        "orders_intro": "**Order Status**\n\nThis table summarizes delivery performance at the order level. Compare the promised completion date with the customer's due date to identify delivery risk.",
        "orders_action": "**Supervisor action**: Prioritize orders with an approaching due date or positive late_days. For Tier-1 orders, delivery impact is especially important because their penalty exposure is higher according to the project economics.",
        "disruptions_intro": "**Disruption Handling**\n\nUse this section when a real-world event makes the current schedule infeasible or risky. Select the type of disruption, provide the event details, and click Replan. The replanner keeps completed and already-started work fixed where required and reschedules affected future work from the disruption time forward.",
        "breakdown_help": "**Machine Breakdown**\n\nUse when a machine becomes unavailable.\n\n**Enter**: machine, breakdown start time, duration\n\nThe replanner treats the machine as unavailable during this interval and moves affected future operations to feasible alternatives where possible.",
        "absence_help": "**Operator Absence**\n\nUse when a qualified operator becomes unavailable.\n\n**Enter**: operator, absence start time, duration\n\nThe replanner prevents that operator from being assigned during the unavailable period and searches for other qualified operators where possible.",
        "material_help": "**Material Delay**\n\nUse when material for an order will not be available at the originally planned time.\n\n**Enter**: order, new material availability time\n\nThe affected order cannot begin material-dependent work before the new availability time.",
        "rework_help": "**Rework**\n\nUse when a quantity of produced material must be processed again.\n\n**Enter**: order, rework quantity\n\nThe rework operation is inserted into the appropriate production flow and becomes new work that must be scheduled.",
        "replan_meaning": "**Replan means**: keep valid historical/completed work fixed, apply the disruption constraints, and generate a new feasible schedule for remaining work.",
        "what_changed": "**What changed?**\n\nCompare the original and replanned schedules to understand which operations moved, whether delivery dates changed, and what additional cost or overtime was introduced by the disruption.",
        "cost_analysis_intro": "**Cost Analysis**\n\nThe scheduler produces three planning strategies. They represent different operational priorities rather than three randomly generated schedules.",
        "cheapest_strategy": "**CHEAPEST**: Prioritizes lower overall economic cost, including operating, operator, overtime, changeover and delivery-penalty effects according to the configured economics.",
        "ontime_strategy": "**MOST ON-TIME**: Prioritizes delivery performance and due-date urgency. It is willing to use different resource assignments and overtime when the scheduling objective favors protecting delivery.",
        "robust_strategy": "**MOST ROBUST**: Prioritizes resilience-related factors such as slack, resource reliability and disruption exposure. It does not guarantee that it will outperform the other strategies in every disruption scenario.",
        "strategy_choice": "**How to choose a strategy**\n\nDo not select a strategy based on one metric alone.\n\n- **Cheapest** is useful when controlling economic cost is the primary concern.\n- **Most On-Time** is useful when protecting customer delivery is the primary concern.\n- **Most Robust** is useful when resilience to future disruption is important.\n\nThe best strategy can depend on the current operating situation and the type of disruption.",
        "recommendation_note": "**Recommendation**\n\nThe recommendation is based on the configured trade-off between economic cost, delivery performance and resilience metrics. This is a decision-support recommendation. The supervisor should review the schedule and operational context before execution.",
        "defense_explanation": "**Defense / System Explanation**\n\nThe application separates planning from execution. The scheduler creates a baseline production plan by assigning operations to compatible machines and qualified operators while respecting routing sequence, material availability, maintenance, breakdowns, shifts and changeovers.\n\nWhen a disruption occurs, the replanner does not simply generate an unrelated new schedule. It applies the disruption to the current state, preserves appropriate historical work, and replans the remaining affected work.\n\nThe three strategy options represent different decision priorities: economic cost, delivery performance and resilience. The dashboard exposes the resulting trade-offs so a supervisor can make an informed operational decision.",
    },
    "Kannada": {
        "briefing": "6 AM ಶಿಫ್ಟ್ ಮಾಹಿತಿ",
        "down": "ಯಂತ್ರ ಸ್ಥಗಿತ",
        "risk": "ಅಪಾಯ",
        "replan": "ಮರುಯೋಜನೆ",
        "recommendation": "ಶಿಫಾರಸು ಮಾಡಿದ ಕ್ರಮ",
        "how_to_use_title": "ಈ ಡ್ಯಾಶ್‌ಬೋರ್ಡ್ ಅನ್ನು ಹೇಗೆ ಬಳಸುವುದು",
        "how_to_use_steps": "ಈ ಡ್ಯಾಶ್‌ಬೋರ್ಡ್ ಅನ್ನು ನಾಲ್ಕು ಹಂತಗಳಲ್ಲಿ ಬಳಸಿ:\n\n1. **ಪ್ರಸ್ತುತ ವೇಳಾಪಟ್ಟಿ ಅನ್ನು ಅವಲೋಕನ ಮಾಡಿ** - ಯಾವ ಯಂತ್ರ, ಆಪರೇಟರ್ ಮತ್ತು ಶಿಫ್ಟ್ ಗೆ ನಿಯೋಜಿತ ಆಗಿದೆ ಎಂಬುದನ್ನು ನೋಡಿ.\n2. **ಆದೇಶಗಳನ್ನು ಪರಿಶೀಲಿಸಿ** - ವಾಗ್ದತ್ತ ಪೂರ್ಣಗೊಳಿಸುವ ದಿನಾಂಕ, ಕಾರ್ಯಾವಧಿ ಮತ್ತು ತಡವನ್ನು ನೋಡಿ.\n3. **ಏನಾದರೂ ತಪ್ಪಾದರೆ**, ಅಡಚಣೆಗಳನ್ನು ತೆರೆಯಿರಿ, ನೈಜ-ವಿಶ್ವ ಅಡಚಣೆಯನ್ನು ಆಯ್ಕೆ ಮಾಡಿ ಮತ್ತು ವಿವರಗಳನ್ನು ನೀಡಿ. ಪೂರ್ಣಗೊಂಡ/ನಡೆಯುತ್ತಿರುವ ಕೆಲಸವನ್ನು ಸಂರಕ್ಷಿಸುತ್ತ ಹೊಸ ಕಾರ್ಯಸಾಧ್ಯ ವೇಳಾಪಟ್ಟಿಯನ್ನು ಉತ್ಪಾದಿಸಲು ಮರುಯೋಜನೆ ಕ್ಲಿಕ್ ಮಾಡಿ.\n4. **ವೆಚ್ಚ ವಿಶ್ಲೇಷಣೆಯನ್ನು ಬಳಸಿ** - ಸಮಯೋಪಯೋಗಿ, ಸುಲಭ ಮತ್ತು ದೃಢ ಯೋಜನೆ ಕಌಶಲ್ಯಗಳನ್ನು ಹೋಲಿಸಿ.",
        "how_to_use_constraints": "**ಮುಖ್ಯ**: ವ್ಯವಸ್ಥೆ ನಿರ್ಬಂಧಗಳನ್ನು ಸ್ವಶಃ ಅಲೆಕ್ಷನೆ ಮಾಡುವುದಿಲ್ಲ. ಯಂತ್ರ ಸಾಮರ್ಥ್ಯ, ಆಪರೇಟರ್ ಯೋಗ್ಯತೆ, ವಸ್ತು ಲಭ್ಯತೆ, ನಿರ್ವಹಣೆ, ಅಡಚಣೆ, ಸಾಲಿನ ಅನುಕ್ರಮ ಮತ್ತು ಶಿಫ್ಟ್/ಓವರ್‌ಟೈಮ್ ನಿಯಮಗಳನ್ನು ವೇಳಾಪಟ್ಟಿ ಮತ್ತು ಮರುಯೋಜನೆ ಪಾರ್ಶ್ವೇನ ಲೆಕ್ಕಾಚಾರ ಮಾಡಲಾಗುತ್ತದೆ.",
    },
    "Tamil": {
        "briefing": "6 AM பணி விளக்கம்",
        "down": "இயந்திரம் செயலிழந்தது",
        "risk": "ஆபத்தில்",
        "replan": "மறுதிட்டமிடு",
        "recommendation": "பரிந்துரைக்கப்பட்ட நடவடிக்கை",
        "how_to_use_title": "இந்த டாஷ்போர்டை எப்படி பயன்படுத்துவது",
        "how_to_use_steps": "இந்த டாஷ்போர்டை நான்கு படிகளில் பயன்படுத்தவும்:\n\n1. **தற்போதைய அட்டவணையை மதிப்பாய்வு செய்யவும்** - ஒவ்வொரு செயல்பாட்டிற்கும் எந்த இயந்திரம், ஆபரேட்டர் மற்றும் ஷிப்ட் ஒதுக்கப்பட்டுள்ளது என்பதைக் காணவும்.\n2. **ஆர்டர்களை சரிபார்க்கவும்** - வாக்குறுதியளிக்கப்பட்ட நிறைவு தேதிகள், காலக்கெடு மற்றும் தாமதங்களைக் காணவும்.\n3. **ஏதேனும் தவறு நிகழ்ந்தால்**, இடையூறுகளைத் திறந்து, உண்மையான-உலக இடையூற்றைத் தேர்ந்தெடுத்து விவரங்களை உள்ளிடவும். நிறைவுசெய்யப்பட்ட/செயல்பாட்டில் இருக்கும் வேலையை பாதுகாக்கும் போது புதிய சாத்தியமான திட்டத்தை உருவாக்க மறுதிட்டமிடு கிளிக் செய்யவும்.\n4. **வீச வாய்ப்பாடு பகுப்பாய்வு பயன்படுத்தவும்** - மலிவு, சிறந்த-நேரத்தில் மற்றும் வலுவான திட்டமிடல் கொள்கைகளை ஒப்பிட்டுப் பாருங்கள்.",
        "how_to_use_constraints": "**முக்கியம்**: கணினி வெளிப்படையாக கட்டுப்பாடுகளை புறக்கணிக்காது. இயந்திர திறன், ஆபரேட்டர் தகுதி, பொருள் கிடைக்கும் தன்மை, பராமரிப்பு, உடைகள், வழிமுறை வரிசை மற்றும் ஷிப்ட்/ஓவர் டைம் விதிகள் அட்டவணையிடல் மற்றும் மறுதிட்டமிடப் போது கருத்தில் கொள்ளப்படுகிறது.",
    },
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


def _slack_days(row) -> float:
    completion = row.get("promised_completion_date")
    if not completion:
        return float("inf")
    return (pd.Timestamp(row["due_date"]) - pd.Timestamp(completion)).total_seconds() / 86400


def _status(row) -> str:
    if row.get("late", False):
        return "CRITICAL"
    if _slack_days(row) < 1:
        return "AT RISK"
    return "ON TRACK"


def _download(label: str, data: bytes, filename: str, mime: str = "text/csv", help: str = None):
    st.download_button(label, data, filename, mime=mime, use_container_width=True, help=help)


def _render_briefing(labels, schedule):
    st.title(labels["briefing"])
    st.caption("Start here at shift change: see the current shift status, critical orders, and what needs your attention.")
    now = st.session_state.current_time
    st.caption(f"{now:%A, %d %b %Y %H:%M}  |  Current shift: {_current_shift(now)}")
    orders = pd.DataFrame(schedule.order_summary)
    orders["slack_days"] = orders.apply(_slack_days, axis=1)
    critical = orders[orders["late"] | (orders["slack_days"] < 1)]
    tier1 = orders[orders["tier"] == "TIER_1"]
    cols = st.columns(4)
    cols[0].metric(
        "Current Shift",
        _current_shift(now),
        help="Which shift is running now (set by the Briefing time control on the left)."
    )
    cols[1].metric(
        "Orders at Risk",
        len(critical),
        help="Count of orders that are already late OR will be late if nothing changes (less than 1 day of buffer remaining)."
    )
    cols[2].metric(
        "Tier-1 Orders",
        len(tier1),
        help="Orders for our JIT customer (highest penalty for lateness). These get priority protection in the plan."
    )
    cols[3].metric(
        "Expected OT",
        f"{sum((x.end_time-x.start_time).total_seconds()/3600 for x in schedule.slots if x.shift_id.endswith('_NIGHT')):.1f} h",
        help="Night shift / overtime hours already baked into the current plan, not a prediction of future overtime."
    )
    st.subheader("What is happening now?")
    st.caption("Live status of every machine on the floor.")
    machine_status = _read_csv("machines.csv")[["machine_id", "machine_type", "status"]]
    st.dataframe(
        machine_status,
        column_config={
            "status": st.column_config.TextColumn(
                "status",
                help="AVAILABLE: ready to use. IN_USE: currently running a job. UNDER_MAINTENANCE: scheduled downtime. BROKEN_DOWN: equipment failure (needs repairs)."
            )
        },
        hide_index=True,
        use_container_width=True
    )
    st.subheader("What is at risk?")
    st.caption("Exactly the orders counted in the 'Orders at Risk' metric above. Each row is an order that needs immediate attention.")
    if critical.empty:
        st.success("All tracked orders are on plan.")
    else:
        display = critical[["order_id", "tier", "due_date", "promised_completion_date", "late_days"]].copy()
        st.dataframe(
            display,
            column_config={
                "late_days": st.column_config.NumberColumn(
                    "late_days",
                    help="0 = on time or early. Positive number = days already late. Negative number = days of buffer still remaining (but still at risk if buffer is less than 1 day)."
                )
            },
            hide_index=True,
            use_container_width=True
        )
    st.subheader(labels["recommendation"])
    st.caption("This is a suggested next action. You still decide what to do.")
    if not critical.empty:
        st.warning("Protect the most time-sensitive Tier-1 work first; review the disruption panel before authorizing overtime.")
    else:
        st.info("Continue the current plan and monitor the grinder and its qualified operators.")
    st.subheader("What changed from the previous plan?")
    st.caption("After you report a disruption (breakdown, absence, delay, rework) in the Disruptions tab and click Replan, this section shows what moved. On a fresh session, nothing has changed yet.")
    if "replan_impact" in st.session_state:
        impact = st.session_state.replan_impact
        st.write(f"{impact['operations_moved']} operations moved; {impact['machine_changes']} machine changes; {impact['operator_changes']} operator changes.")
    else:
        st.write("No disruption has been applied in this session.")


def _render_schedule(labels, schedule):
    st.header("Schedule")
    st.caption("The complete machine-by-machine, shift-by-shift plan for the currently selected planning policy.")
    st.markdown(labels.get("schedule_intro", ""))
    with st.expander("How to read this schedule", expanded=False):
        st.markdown(labels.get("schedule_how_to_read", ""))
    frame = schedule_dataframe(schedule)
    machines = st.multiselect(
        "Machine",
        sorted(frame["machine_id"].unique()),
        help="Filter to show only these machines. Leave empty to show all."
    )
    shifts = st.multiselect(
        "Shift",
        sorted(frame["shift_id"].unique()),
        help="Filter to show only these shifts (MORNING / AFTERNOON / NIGHT). Leave empty to show all."
    )
    orders = st.multiselect(
        "Order",
        sorted(frame["order_id"].unique()),
        help="Filter to show only these orders. Leave empty to show all."
    )
    if machines: frame = frame[frame.machine_id.isin(machines)]
    if shifts: frame = frame[frame.shift_id.isin(shifts)]
    if orders: frame = frame[frame.order_id.isin(orders)]
    shown = frame[["machine_id", "machine_type", "shift_id", "order_id", "operation_id", "start_time", "end_time", "operator_id", "setup_time_minutes", "status"]]
    display = shown.copy()
    for source_col, date_label, time_label in [
        ("start_time", "Start Date", "Start Time"),
        ("end_time", "End Date", "End Time"),
    ]:
        source = pd.to_datetime(display[source_col], errors="coerce")
        display[date_label] = source.dt.strftime("%Y-%m-%d")
        display[time_label] = source.dt.strftime("%H:%M:%S")
    display = display[[
        "machine_id",
        "machine_type",
        "shift_id",
        "order_id",
        "operation_id",
        "Start Date",
        "Start Time",
        "End Date",
        "End Time",
        "operator_id",
        "setup_time_minutes",
        "status",
    ]]
    st.dataframe(
        display,
        column_config={
            "machine_id": st.column_config.TextColumn(
                "machine_id",
                help="Physical machine assigned to this operation."
            ),
            "machine_type": st.column_config.TextColumn(
                "machine_type",
                help="Machine capability/type required by the operation."
            ),
            "shift_id": st.column_config.TextColumn(
                "shift_id",
                help="Production shift containing the scheduled work."
            ),
            "order_id": st.column_config.TextColumn(
                "order_id",
                help="Customer order being manufactured."
            ),
            "operation_id": st.column_config.TextColumn(
                "operation_id",
                help="Unique identifier of the operation."
            ),
            "Start Date": st.column_config.TextColumn(
                "Start Date",
                help="Planned start time (the time the system thinks this will begin). This is planned, not actual."
            ),
            "Start Time": st.column_config.TextColumn(
                "Start Time",
                help="Planned start time (the time the system thinks this will begin). This is planned, not actual."
            ),
            "End Date": st.column_config.TextColumn(
                "End Date",
                help="Planned end time (the time the system thinks this will finish). This is planned, not actual."
            ),
            "End Time": st.column_config.TextColumn(
                "End Time",
                help="Planned end time (the time the system thinks this will finish). This is planned, not actual."
            ),
            "setup_time_minutes": st.column_config.NumberColumn(
                "setup_time_minutes",
                help="Changeover time (in minutes) that must happen before this operation can start."
            ),
            "status": st.column_config.TextColumn(
                "status",
                help="Current status of this operation: SCHEDULED, IN_PROGRESS, COMPLETED, or BLOCKED."
            ),
            "operator_id": st.column_config.TextColumn(
                "operator_id",
                help="Qualified operator assigned to run this operation. This is a label, not editable."
            )
        },
        hide_index=True,
        use_container_width=True
    )
    _download(
        "Download current schedule CSV",
        shown.to_csv(index=False).encode(),
        "current_schedule.csv",
        help="Exports only the rows currently shown on screen after any filters, not the full unfiltered schedule."
    )
    st.subheader("Machine × Shift")
    st.caption("Each cell shows how many operations are scheduled on that machine in that shift. Busier machines stand out.")
    matrix = shown.pivot_table(index="machine_id", columns="shift_id", values="operation_id", aggfunc="count", fill_value=0)
    st.dataframe(matrix, use_container_width=True)


def _render_orders(labels, schedule):
    st.header("Orders")
    st.caption("One row per order, showing its current risk status across the entire order book, not just the at-risk ones.")
    st.markdown(labels.get("orders_intro", ""))
    orders = _read_csv("orders.csv")
    customers = _read_csv("customers.csv")[["customer_id", "name", "tier"]]
    summary = pd.DataFrame(schedule.order_summary)
    frame = orders.merge(customers, on="customer_id").merge(summary[["order_id", "promised_completion_date", "late_days", "late"]], on="order_id")
    frame["status"] = frame.apply(_status, axis=1)
    frame["risk"] = frame["status"]
    tiers = st.multiselect(
        "Customer tier",
        sorted(frame["tier"].unique()),
        help="Filter to show only these customer tiers. Leave empty to show all."
    )
    if tiers: frame = frame[frame.tier.isin(tiers)]
    frame = frame.sort_values(["risk", "due_date"])
    st.dataframe(
        frame[["order_id", "name", "tier", "quantity", "due_date", "promised_completion_date", "late_days", "status", "priority", "risk"]],
        column_config={
            "order_id": st.column_config.TextColumn(
                "order_id",
                help="Unique production order identifier."
            ),
            "tier": st.column_config.TextColumn(
                "tier",
                help="Customer priority/tier used by the scheduling and delivery-cost model."
            ),
            "due_date": st.column_config.TextColumn(
                "due_date",
                help="Customer-required completion date."
            ),
            "promised_completion_date": st.column_config.TextColumn(
                "promised_completion_date",
                help="Date/time the scheduler currently expects the final operation to finish. Calculated from the schedule."
            ),
            "priority": st.column_config.TextColumn(
                "priority",
                help="How heavily the scheduler weights this order when machines are contested. Higher priority = gets first pick of machine time."
            ),
            "late_days": st.column_config.NumberColumn(
                "late_days",
                help="0 = on time or early. Positive = days already late. Negative = days of buffer remaining before due date."
            ),
            "status": st.column_config.TextColumn(
                "status",
                help="Current delivery risk: CRITICAL (already late), AT RISK (less than 1 day buffer), ON TRACK (plenty of buffer)."
            ),
            "risk": st.column_config.TextColumn(
                "risk",
                help="Same as 'status'—these two columns are intentionally identical. Read whichever one is clearer to you."
            )
        },
        hide_index=True,
        use_container_width=True
    )
    st.info(labels.get("orders_action", ""))
    _download(
        "Download order summary CSV",
        frame.to_csv(index=False).encode(),
        "order_summary.csv",
        help="Exports the currently filtered view (if you applied any tier filters), same as the Schedule tab."
    )


def _make_disruptions(kind: str, values: dict) -> list[Disruption]:
    when = values["start"]
    if kind == "Machine breakdown":
        return [Disruption("UI_BREAKDOWN", DisruptionType.MACHINE_BREAKDOWN, when, values["machine"], values["duration"], f"{values['machine']} unavailable")]
    if kind == "Operator absence":
        return [Disruption("UI_ABSENCE", DisruptionType.OPERATOR_ABSENCE, when, values["operator"], values["duration"], f"{values['operator']} absent")]
    if kind == "Material delay":
        return [Disruption("UI_MATERIAL", DisruptionType.MATERIAL_DELAY, values["available"], values["order"], 0, f"Material delayed for {values['order']}")]
    if kind == "Power cut":
        return [Disruption("UI_POWER_CUT", DisruptionType.POWER_CUT, when, "SHOP", values["duration"], "Grid power cut shop-wide", generator_available=values["generator_available"])]
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
    st.caption("Tell the system something went wrong on the floor. Fill in the details, click Replan, and the schedule will recalculate around the disruption.")
    st.markdown(labels.get("disruptions_intro", ""))
    machines = _read_csv("machines.csv")["machine_id"].tolist()
    operators = _read_csv("operators.csv")["operator_id"].tolist()
    orders = _read_csv("orders.csv")["order_id"].tolist()
    kind = st.selectbox(
        "Disruption type",
        ["Machine breakdown", "Operator absence", "Material delay", "Rework", "Power cut", "Combined / cascade"],
        help="Machine breakdown: equipment stops working. Operator absence: person is unavailable. Material delay: incoming part arrives late. Rework: pieces failed inspection and must be redone. Power cut: choose generator operation or lose the outage window. Combined/cascade: grinder and one operator both go down at the same time."
    )
    # Show help for selected disruption type
    if kind == "Machine breakdown":
        with st.expander("What is Machine Breakdown?", expanded=False):
            st.markdown(labels.get("breakdown_help", ""))
    elif kind == "Operator absence":
        with st.expander("What is Operator Absence?", expanded=False):
            st.markdown(labels.get("absence_help", ""))
    elif kind == "Material delay":
        with st.expander("What is Material Delay?", expanded=False):
            st.markdown(labels.get("material_help", ""))
    elif kind == "Rework":
        with st.expander("What is Rework?", expanded=False):
            st.markdown(labels.get("rework_help", ""))
    
    start_date = st.date_input(
        "Start date",
        st.session_state.current_time.date(),
        help="When did the disruption start (or will it start)?"
    )
    start_time = st.time_input(
        "Start time",
        st.session_state.current_time.time(),
        help="At what time did the disruption start (or will it start)?"
    )
    start = datetime.combine(start_date, start_time)
    duration = st.number_input(
        "Duration (hours)",
        min_value=1.0,
        max_value=72.0,
        value=8.0,
        step=1.0,
        help="How long will the disruption last (in hours)? Only relevant for breakdowns and absences."
    )
    values = {"start": start, "duration": duration}
    if kind == "Machine breakdown":
        values["machine"] = st.selectbox(
            "Machine",
            machines,
            help="Which machine broke down?"
        )
    elif kind == "Operator absence":
        values["operator"] = st.selectbox(
            "Operator",
            operators,
            help="Which operator is unavailable?"
        )
    elif kind == "Material delay":
        values["order"] = st.selectbox(
            "Order",
            orders,
            help="Which order's material is delayed?"
        )
        values["available"] = st.datetime_input(
            "New material availability",
            start + timedelta(days=1),
            help="When will the delayed material actually arrive?"
        )
    elif kind == "Rework":
        values["order"] = st.selectbox(
            "Order",
            orders,
            help="Which order failed quality and needs rework?"
        )
        values["quantity"] = st.number_input(
            "Rework quantity",
            min_value=1,
            value=40,
            step=1,
            help="How many pieces failed and must be redone?"
        )
    elif kind == "Power cut":
        values["generator_available"] = st.radio(
            "Power cut response",
            [True, False],
            format_func=lambda value: "Run diesel generator" if value else "Lose the outage window",
            help="Generator uses the configured 1.8x effective machine rate. Losing the window delays work and may increase delivery penalties."
        )
    elif kind == "Combined / cascade":
        values["operator"] = st.selectbox(
            "Absent grinder operator",
            operators,
            index=min(operators.index("OP_001"), len(operators)-1) if "OP_001" in operators else 0,
            help="This scenario has the grinder machine DOWN plus this operator absent at the same time—the worst combination. Which operator is unavailable?"
        )
    
    st.info(labels.get("replan_meaning", ""))
    
    if st.button(
        labels["replan"],
        type="primary",
        use_container_width=True,
        help="Nothing changes until you click this. Calculates a new schedule around the disruption you described above."
    ):
        if kind == "Combined / cascade":
            _run_replan([Disruption("UI_CASCADE_BREAKDOWN", DisruptionType.MACHINE_BREAKDOWN, start, "GRINDER_01", duration, "Grinder breakdown"), Disruption("UI_CASCADE_ABSENCE", DisruptionType.OPERATOR_ABSENCE, start, values["operator"], duration, "Operator absence")])
        else:
            _run_replan(_make_disruptions(kind, values), values.get("quantity"))
    if st.button(
        "RUN MIRAI DEFENSE SCENARIO",
        use_container_width=True,
        help="Loads one fixed demo scenario (grinder down Tuesday 11 AM, grinder-qualified operator absent, Thursday Tier-1 delivery at risk) as a pre-built test. Ignores everything else you entered above."
    ):
        _run_replan([Disruption("UI_DEFENSE_BREAKDOWN", DisruptionType.MACHINE_BREAKDOWN, DEFENSE_TIME, "GRINDER_01", 8, "Tuesday 11 AM grinder breakdown"), Disruption("UI_DEFENSE_ABSENCE", DisruptionType.OPERATOR_ABSENCE, DEFENSE_TIME, "OP_001", 8, "Grinder-qualified operator absent")])
    if "replan_impact" in st.session_state:
        st.subheader("BEFORE ↑ DISRUPTION ↑ AFTER")
        st.markdown(labels.get("what_changed", ""))
        impact = st.session_state.replan_impact
        st.json({key: value for key, value in impact.items() if key != "wasted_changeover"})
        st.text_area(
            "Replan explanation",
            st.session_state.replan_explanation,
            height=220,
            help="Plain-English summary: here is what shifted in the plan and why. Hand this to the supervisor on the floor if needed."
        )
        _download(
            "Download disruption impact",
            json_bytes(impact),
            "disruption_impact.json",
            "application/json",
            help="Exports the JSON impact summary above as a file for record-keeping."
        )


def json_bytes(value):
    import json
    return (json.dumps(value, indent=2, default=str) + "\n").encode()


def _render_costs(labels):
    st.header("Cost & Trade-offs")
    st.caption("Side-by-side comparison of all three planning policies on the same 25 orders. Not just the one currently selected in the sidebar.")
    st.markdown(labels.get("cost_analysis_intro", ""))
    
    with st.expander("Understanding the three strategies", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(labels.get("cheapest_strategy", ""))
        with col2:
            st.markdown(labels.get("ontime_strategy", ""))
        with col3:
            st.markdown(labels.get("robust_strategy", ""))
    
    st.markdown(labels.get("strategy_choice", ""))
    
    path = OUTPUT_DIR / "strategy_comparison.csv"
    comparison = pd.read_csv(path) if path.exists() else pd.DataFrame()
    if comparison.empty:
        st.warning("Strategy comparison is not available yet.")
        return
    st.dataframe(
        comparison,
        column_config={
            "Total Tardiness (days)": st.column_config.NumberColumn(
                "Total Tardiness (days)",
                help="Sum of days late across all late orders (not an average; one order 3 days late + one order 2 days late = 5 total tardiness)."
            ),
            "Maximum Lateness (days)": st.column_config.NumberColumn(
                "Maximum Lateness (days)",
                help="The worst single order's lateness in days. Even one critical order can damage reputation."
            ),
            "Average Slack (days)": st.column_config.NumberColumn(
                "Average Slack (days)",
                help="Average days of buffer before due date across all orders. Positive = safe, negative = some orders already late."
            ),
            "Minimum Slack (days)": st.column_config.NumberColumn(
                "Minimum Slack (days)",
                help="Buffer on the tightest (most at-risk) order. This is your warning: a negative number here means the worst case is already late."
            ),
            "Grinder Utilization (%)": st.column_config.NumberColumn(
                "Grinder Utilization (%)",
                help="Percentage of grinder machine's available hours that are scheduled. 100% = fully booked, no gaps."
            ),
            "Grinder-Operator Utilization (%)": st.column_config.NumberColumn(
                "Grinder-Operator Utilization (%)",
                help="Percentage of grinder-qualified operator labor hours that are scheduled. This is different from machine utilization: it's the 3-person labor ceiling, not just the grinder machine itself."
            ),
            "Bottleneck Utilization (%)": st.column_config.NumberColumn(
                "Bottleneck Utilization (%)",
                help="Percentage of the busiest resource (machine or labor). No plan can be more than 100% used here."
            ),
            "Unscheduled Operations": st.column_config.NumberColumn(
                "Unscheduled Operations",
                help="Should always be 0. If not 0, something is wrong—operations exist that couldn't fit into the plan."
            ),
            "Completion Rate (%)": st.column_config.NumberColumn(
                "Completion Rate (%)",
                help="Percentage of operations that can be finished within the schedule horizon. Below 100% means some work cannot fit."
            )
        },
        hide_index=True,
        use_container_width=True
    )
    _download(
        "Download cost comparison CSV",
        comparison.to_csv(index=False).encode(),
        "strategy_comparison.csv",
        help="Exports this full table as-is for further analysis or record-keeping."
    )
    st.subheader("Recommended policy")
    st.markdown(labels.get("recommendation_note", ""))
    best = comparison.sort_values(["Late Orders", "Total Cost (INR)"]).iloc[0]
    st.info(f"{best['Strategy']} currently offers the best delivery-first balance: {int(best['Late Orders'])} late orders at ₹{best['Total Cost (INR)']:,.2f}.")
    st.write("CHEAPEST saves operating and changeover cost but accepts more penalty exposure. MOST_ON_TIME spends more to protect delivery. MOST_ROBUST trades efficiency for slack and recovery flexibility; resilience results should guide the final policy choice.")


def _render_memo(labels):
    st.header("Final Recommendation / Trade-off Memo")
    st.caption("The full written justification for the recommended policy, generated fresh from the same numbers shown in the Cost & Trade-offs tab.")
    schedules = {strategy: _baseline(strategy) for strategy in STRATEGIES}
    memo = generate_memo(schedules["CHEAPEST"], schedules["MOST_ON_TIME"], schedules["MOST_ROBUST"])
    recommendation = next((line.removeprefix("The recommended operating policy is **").split("**", 1)[0] for line in memo.splitlines() if line.startswith("The recommended operating policy is")), "See memo")
    st.success(f"Recommended strategy: {recommendation}")
    st.caption("Same recommendation as the Cost & Trade-offs tab, with full reasoning below instead of raw numbers.")
    st.markdown(memo)
    _download("Download final trade-off memo", memo.encode(), "final_tradeoff_memo.md", "text/markdown", help="Exports this memo as a Markdown file for printing or sharing with the team.")
    
    st.divider()
    with st.expander("Defense / System Explanation", expanded=False):
        st.markdown(labels.get("defense_explanation", ""))


def main():
    st.set_page_config(page_title="Mirai Machine Shop", page_icon="⚙", layout="wide", initial_sidebar_state="expanded")
    st.markdown("""<style>h1 {font-size: 2.2rem;} .stMetric {border-left: 4px solid #0f766e; padding-left: 12px;} [data-testid='stDataFrame'] {font-size: 0.88rem;}</style>""", unsafe_allow_html=True)
    if "strategy" not in st.session_state: st.session_state.strategy = "MOST_ON_TIME"
    if "current_time" not in st.session_state: st.session_state.current_time = datetime(2026, 9, 1, 6)
    with st.sidebar:
        st.header("Mirai Shop Floor")
        st.caption("Use these controls to set the plan to display, choose language, and set the current time across all tabs below.")
        st.session_state.strategy = st.selectbox(
            "Planning policy",
            STRATEGIES,
            index=STRATEGIES.index(st.session_state.strategy),
            help="CHEAPEST: lowest cost, more risk of late orders. MOST_ON_TIME: protects delivery deadlines, higher cost. MOST_ROBUST: safest against breakdowns, maximum slack and flexibility."
        )
        language = st.selectbox(
            "Language",
            list(LABELS),
            help="Changes only the display labels and section headings on screen; all underlying data and IDs remain the same."
        )
        st.session_state.current_time = st.datetime_input(
            "Briefing time",
            st.session_state.current_time,
            help="Sets the current time for the entire dashboard. This determines what counts as already-happened vs. still-upcoming everywhere on screen."
        )
        st.caption("Static operational labels only. IDs and data remain unchanged.")
    
    labels = LABELS[language]
    
    # Add "How to use" section at the top
    with st.expander(labels.get("how_to_use_title", "How to use this dashboard"), expanded=False):
        st.markdown(labels.get("how_to_use_steps", ""))
        st.divider()
        st.markdown(labels.get("how_to_use_constraints", ""))
    
    schedule = _active_schedule()
    tabs = st.tabs([labels["briefing"], "Schedule", "Orders", "Disruptions", "Cost & Trade-offs", "Final Recommendation"])
    with tabs[0]: _render_briefing(labels, schedule)
    with tabs[1]: _render_schedule(labels, schedule)
    with tabs[2]: _render_orders(labels, schedule)
    with tabs[3]: _render_disruptions(labels)
    with tabs[4]: _render_costs(labels)
    with tabs[5]: _render_memo(labels)


if __name__ == "__main__":
    main()