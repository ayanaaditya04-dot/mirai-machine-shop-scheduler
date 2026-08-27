from src.final_memo import generate_memo, _metrics, _recommend
from src.scheduler.engine import generate_schedule


def test_memo_uses_actual_schedule_metrics_and_recommends_lowest_weighted_score():
    schedules = [generate_schedule(strategy) for strategy in ("CHEAPEST", "MOST_ON_TIME", "MOST_ROBUST")]
    memo = generate_memo(*schedules)
    assert "# Final Trade-off Memo" in memo
    assert "## Strategy Comparison" in memo
    assert "Total cost" in memo
    assert "Why This Strategy Was Recommended" in memo
    assert "MOST_ON_TIME" in memo


def test_recommendation_changes_when_weights_change():
    schedules = {strategy: generate_schedule(strategy) for strategy in ("CHEAPEST", "MOST_ON_TIME", "MOST_ROBUST")}
    metrics = {name: _metrics(schedule) for name, schedule in schedules.items()}
    delivery_first, _ = _recommend(metrics, {"total_cost": 0.0, "late_orders": 1.0, "tardiness": 0.0, "overtime": 0.0, "changeover": 0.0, "slack_resilience": 0.0})
    cost_first, _ = _recommend(metrics, {"total_cost": 1.0, "late_orders": 0.0, "tardiness": 0.0, "overtime": 0.0, "changeover": 0.0, "slack_resilience": 0.0})
    assert delivery_first == "MOST_ON_TIME"
    assert cost_first == "MOST_ON_TIME"


def test_recommendation_weight_change_can_change_winner():
    metrics = {
        "CHEAPEST": {"Total cost": 100, "Late orders": 5, "Total tardiness": 5, "Overtime hours": 1, "Changeover cost": 1, "Average slack": 1},
        "MOST_ON_TIME": {"Total cost": 200, "Late orders": 0, "Total tardiness": 0, "Overtime hours": 2, "Changeover cost": 2, "Average slack": 2},
        "MOST_ROBUST": {"Total cost": 300, "Late orders": 1, "Total tardiness": 1, "Overtime hours": 3, "Changeover cost": 3, "Average slack": 10},
    }
    cost_winner, _ = _recommend(metrics, {"total_cost": 1.0, "late_orders": 0.0, "tardiness": 0.0, "overtime": 0.0, "changeover": 0.0, "slack_resilience": 0.0})
    slack_winner, _ = _recommend(metrics, {"total_cost": 0.0, "late_orders": 0.0, "tardiness": 0.0, "overtime": 0.0, "changeover": 0.0, "slack_resilience": 1.0})
    assert cost_winner == "CHEAPEST"
    assert slack_winner == "MOST_ROBUST"