from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Permission:
    name: str


ROLE_PERMISSIONS = {
    "support_agent": {
        "view_orders",
        "view_customer_history",
        "check_inventory",
        "create_approval_request",
        "view_own_approvals",
    },
    "operations_manager": {
        "view_orders",
        "view_customer_history",
        "check_inventory",
        "create_approval_request",
        "approve_approval_request",
        "reject_approval_request",
        "view_all_approvals",
    },
    "finance_analyst": {
        "view_orders",
        "view_customer_history",
        "view_financial_metrics",
        "view_all_approvals",
    },
}


def can_user_perform(username: str, role: str, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())


def allowed_pages_for_role(role: str) -> list[str]:
    if role == "support_agent":
        return ["operations", "approval_center", "audit_log"]
    if role == "operations_manager":
        return ["operations", "approval_center", "metrics", "audit_log"]
    if role == "finance_analyst":
        return ["metrics", "audit_log"]
    return ["operations"]
