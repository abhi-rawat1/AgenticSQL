from langchain.tools import tool

from core.guardrails import validate_sql_query
from services.db import execute_read_query, fetch_table_schema

@tool
def execute_read_query_tool(sql: str):
    """Execute a read-only SQL query and return the results."""
    print(f"Executing SQL query **** : {sql}")
    guard = validate_sql_query(sql)
    sql = sql.replace("```sql", "").replace("```", "").strip().lower()
    if not guard.allowed:
        return {"error": guard.reason}
    return execute_read_query(sql)

@tool
def lookup_order(order_id: str):
    """Fetch a single order and its key metadata by order ID."""
    query = f"SELECT * FROM orders WHERE order_id = '{order_id}' LIMIT 10;"
    guard = validate_sql_query(query)
    if not guard.allowed:
        return {"error": guard.reason}
    return execute_read_query(query)


@tool
def lookup_customer_orders(customer_id: str):
    """Return recent orders for a customer."""
    query = f"SELECT * FROM orders WHERE customer_id = '{customer_id}' ORDER BY order_date DESC LIMIT 20;"
    guard = validate_sql_query(query)
    if not guard.allowed:
        return {"error": guard.reason}
    return execute_read_query(query)


@tool
def check_inventory(product_sku: str):
    """Looks up current inventory for a product by SKU."""
    query = f"SELECT * FROM inventory WHERE sku = '{product_sku}' OR product_id = '{product_sku}' LIMIT 10;"
    guard = validate_sql_query(query)
    if not guard.allowed:
        return {"error": guard.reason}
    return execute_read_query(query)


@tool
def get_support_schema():
    """Return the supported ecommerce schema for the support agent."""
    return fetch_table_schema()


@tool
def get_metric(metric_name: str):
    """Return a semantic metric defined in the DBT model layer."""
    from services.metrics_service import metric_lookup

    return metric_lookup(metric_name)
