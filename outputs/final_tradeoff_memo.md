# Final Trade-off Memo

## Executive Summary

The recommended operating policy is **MOST_ON_TIME**. This recommendation is calculated from the actual generated schedules, their cost breakdowns, delivery results, operating hours, and slack. No strategy is forced to win.

## Strategy Comparison

| Strategy | Total cost | Machine cost | Operator cost | Overtime cost | Changeover cost | Penalty cost | Overtime hours | Late orders | Total tardiness | Maximum lateness | On-time orders | Average slack | Machine utilization | Grinder utilization | Unscheduled operations |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CHEAPEST | 392549.43 | 206920.35 | 49535.6 | 14633.95 | 41791.17 | 79668.36 | 84.806 | 7 | 28.709 | 6.87 | 18 | 2.982 | 12.48 | 89.071 | 0 |
| MOST_ON_TIME | 375490.9 | 206170.61 | 57391.32 | 12478.78 | 67916.67 | 31533.53 | 66.766 | 4 | 11.742 | 5.673 | 21 | 1.418 | 13.304 | 89.071 | 0 |
| MOST_ROBUST | 389834.89 | 205505.0 | 50115.07 | 15650.09 | 38561.08 | 80003.64 | 101.692 | 8 | 26.7 | 5.792 | 17 | 2.982 | 12.405 | 89.071 | 0 |

## Weighted Recommendation

The configured recommendation weights are:

- `total_cost`: 35%
- `late_orders`: 25%
- `tardiness`: 15%
- `overtime`: 5%
- `changeover`: 5%
- `slack_resilience`: 15%

Scores are normalized across the three actual schedules. Lower is better for cost, late orders, tardiness, overtime, and changeover. Higher average slack is better for resilience.

- **MOST_ON_TIME**: `0.200000`
- **CHEAPEST**: `0.718828`
- **MOST_ROBUST**: `0.726543`

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

It has the strongest weighted result because it protects delivery while also performing competitively on total cost in this dataset.

For a factory owner or supervisor, the practical reading is: choose **MOST_ON_TIME** for this planning horizon because it gives the best balance of the business outcomes represented by the configured weights. Re-evaluate the choice when order mix, due dates, costs, or disruption exposure changes.

## Limitations

- This recommendation depends on the current generated dataset.
- It depends on the configured economic and business weights.
- The score is a transparent decision aid, not a guarantee of future schedule performance.
- Robustness is represented by available schedule metrics; future disruption scenarios may change the preferred policy.
