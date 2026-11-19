import re
from dataclasses import dataclass
from typing import Any

from config import settings


BLOCKED_PATTERNS = [
    r"\bDROP\b",
    r"\bDELETE\b",
    r"\bUPDATE\b",
    r"\bINSERT\b",
    r"\bALTER\b",
    r"\bTRUNCATE\b",
    r"\bGRANT\b",
    r"\bREVOKE\b",
    r"\bCREATE\s+TABLE\b",
    r"\bCREATE\s+VIEW\b",
]


@dataclass
class GuardrailResult:
    allowed: bool
    reason: str | None = None
    sanitized_sql: str | None = None
    action_name: str | None = None


def validate_sql_query(sql: str) -> GuardrailResult:
    normalized = sql.strip()
    if not normalized:
        return GuardrailResult(False, "Empty SQL query.")

    if len(normalized) > 20000:
        return GuardrailResult(False, "SQL is too large.")

    upper_sql = normalized.upper()
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, upper_sql):
            return GuardrailResult(False, f"Blocked statement matches forbidden pattern: {pattern}.")

    for table in _extract_table_names(normalized):
        if table.lower() not in {t.lower() for t in settings.allowed_tables}:
            return GuardrailResult(False, f"Table '{table}' is not allowed by policy.")

    return GuardrailResult(True, None, normalized, None)


def require_action_approval(action_name: str, approved: bool) -> GuardrailResult:
    if action_name in settings.approval_required_actions and not approved:
        return GuardrailResult(False, f"Action '{action_name}' requires approval before execution.")
    return GuardrailResult(True, None, None, action_name)


def detect_action_intent(message: str) -> str | None:
    lowered = message.lower()
    intent_map = {
        "refund_order": ["refund", "issue refund", "refund order"],
        "create_return": ["return order", "initiate return", "create return"],
        "cancel_order": ["cancel order", "stop order"],
        "update_inventory": ["update inventory", "adjust stock"],
    }
    for action_name, keywords in intent_map.items():
        if any(keyword in lowered for keyword in keywords):
            return action_name
    return None


def _extract_table_names(sql: str) -> list[str]:
    matches = re.findall(r"from\s+([A-Za-z_][A-Za-z0-9_]*)|join\s+([A-Za-z_][A-Za-z0-9_]*)", sql, flags=re.IGNORECASE)
    flattened = []
    for item in matches:
        for value in item:
            if value:
                flattened.append(value)
    return flattened
