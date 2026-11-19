from core.guardrails import validate_sql_query
from services.approval_service import create_approval_request, update_approval_status
from services.auth_service import authenticate_support_agent


def test_block_destructive_sql():
    result = validate_sql_query("DELETE FROM orders WHERE order_id = 1")
    assert result.allowed is False
    assert "forbidden" in result.reason.lower()


def test_allow_read_only_sql():
    result = validate_sql_query("SELECT * FROM orders WHERE order_id = 10021 LIMIT 5")
    assert result.allowed is True


def test_reject_unknown_table():
    result = validate_sql_query("SELECT * FROM forbidden_table LIMIT 5")
    assert result.allowed is False


def test_approval_status_change_round_trip():
    request = create_approval_request("10021", "refund_order", "Damaged item", "support-agent")
    updated = update_approval_status(request["request_id"], "approved", "ops-manager", "Approved after review")
    assert updated["status"] == "approved"
    assert updated["approved_by"] == "ops-manager"
    assert updated["comments"] == "Approved after review"


def test_authentication_for_support_agents():
    user = authenticate_support_agent("ops_manager", "ops123")
    assert user["username"] == "ops_manager"
    assert user["role"] == "operations_manager"
    assert "token" in user
