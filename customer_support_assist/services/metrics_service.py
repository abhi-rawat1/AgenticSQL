from typing import Any

from services.db import execute_read_query


SEMANTIC_METRICS = {
    "total_revenue": "SELECT COALESCE(SUM(total_amount), 0) AS total_revenue FROM orders WHERE order_date >= CURRENT_DATE - INTERVAL '30 days'",
    "orders_count": "SELECT COUNT(*) AS orders_count FROM orders WHERE order_date >= CURRENT_DATE - INTERVAL '30 days'",
    "return_rate": "SELECT ROUND((COUNT(CASE WHEN status = 'returned' THEN 1 END)::numeric / NULLIF(COUNT(*), 0)) * 100, 2) AS return_rate FROM orders WHERE order_date >= CURRENT_DATE - INTERVAL '30 days'",
    "avg_order_value": "SELECT ROUND(AVG(total_amount), 2) AS avg_order_value FROM orders WHERE order_date >= CURRENT_DATE - INTERVAL '30 days'",
    "refund_resolution_time_days": "SELECT ROUND(AVG(EXTRACT(DAY FROM resolved_at - created_at)), 2) AS refund_resolution_time_days FROM refunds WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'",
}


def metric_lookup(metric_name: str) -> dict[str, Any]:
    if metric_name not in SEMANTIC_METRICS:
        raise ValueError(f"Unsupported semantic metric: {metric_name}")
    rows = execute_read_query(SEMANTIC_METRICS[metric_name])
    return {"metric_name": metric_name, "result": rows}
