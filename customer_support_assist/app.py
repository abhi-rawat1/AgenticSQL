import json
import os
from pathlib import Path
from urllib import error, request

import pandas as pd
import streamlit as st

from services.approval_service import (
    approve_request,
    cancel_request,
    create_approval_request,
    list_all_approvals,
    list_pending_approvals,
    reject_request,
)
from services.auth_service import authenticate_support_agent
from workflows.support_workflow import process_support_request, resume_support_request

API_BASE_URL = os.getenv("CUSTOMER_SUPPORT_API_URL", "http://localhost:8000")


def api_request(method: str, path: str, payload: dict | None = None, token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    api_url = f"{API_BASE_URL}{path}"
    req = request.Request(api_url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
            raise ValueError(payload.get("detail", "Request failed")) from exc
        except Exception:
            raise ValueError(str(exc)) from exc
    except Exception:
        return None


def login_support_user(username: str, password: str):
    response = api_request("POST", "/login", {"username": username, "password": password})
    if response and "user" in response and "access_token" in response:
        user = response["user"]
        user["token"] = response["access_token"]
        return user
    user = authenticate_support_agent(username, password)
    if user:
        return user
    raise ValueError("Invalid username or password")


def list_pending_approvals_for_ui():
    token = st.session_state.get("access_token")
    response = api_request("GET", "/approvals/pending", token=token)
    if response and "approvals" in response:
        return response["approvals"]
    return list_pending_approvals()


def list_all_approvals_for_ui():
    token = st.session_state.get("access_token")
    response = api_request("GET", "/approvals", token=token)
    if response and "approvals" in response:
        return response["approvals"]
    return list_all_approvals()


def create_approval_request_for_ui(order_id: str, action_type: str, reason: str, requested_by: str):
    token = st.session_state.get("access_token")
    response = api_request(
        "POST",
        "/approvals",
        {"order_id": order_id, "action_type": action_type, "reason": reason, "requested_by": requested_by},
        token=token,
    )
    if response:
        return response
    return create_approval_request(order_id, action_type, reason, requested_by)


def approve_request_for_ui(request_id: str, approved_by: str, comments: str):
    token = st.session_state.get("access_token")
    response = api_request(
        "POST",
        "/approvals/decision",
        {"request_id": request_id, "approved_by": approved_by, "decision": "approved", "comments": comments},
        token=token,
    )
    if response:
        return response
    return approve_request(request_id, approved_by, comments)


def reject_request_for_ui(request_id: str, approved_by: str, comments: str):
    token = st.session_state.get("access_token")
    response = api_request(
        "POST",
        "/approvals/decision",
        {"request_id": request_id, "approved_by": approved_by, "decision": "rejected", "comments": comments},
        token=token,
    )
    if response:
        return response
    return reject_request(request_id, approved_by, comments)


def cancel_request_for_ui(request_id: str, approved_by: str, comments: str):
    token = st.session_state.get("access_token")
    response = api_request(
        "POST",
        "/approvals/decision",
        {"request_id": request_id, "approved_by": approved_by, "decision": "cancelled", "comments": comments},
        token=token,
    )
    if response:
        return response
    return cancel_request(request_id, approved_by, comments)


def render_query_result(response: dict):
    rows = response.get("rows", [])
    presentation = response.get("presentation")
    sql = response.get("sql")

    if sql:
        with st.expander("Generated SQL"):
            st.code(sql, language="sql")

    if not rows:
        st.info(response.get("answer", "No results found."))
        return

    df = pd.DataFrame(rows)
    if not presentation:
        st.dataframe(df, use_container_width=True)
        return

    output_format = presentation.get("format", "table")
    title = presentation.get("title")
    if title:
        st.subheader(title)

    x_field = presentation.get("x_field")
    y_field = presentation.get("y_field")

    if output_format == "table":
        st.dataframe(df, use_container_width=True)
    elif output_format == "line_chart" and x_field in df.columns and y_field in df.columns:
        st.line_chart(df.set_index(x_field)[y_field])
    elif output_format == "bar_chart" and x_field in df.columns and y_field in df.columns:
        st.bar_chart(df.set_index(x_field)[y_field])
    elif output_format == "metric" and len(df.columns) == 1:
        st.metric(title or "Metric", df.iloc[0, 0])
    else:
        st.dataframe(df, use_container_width=True)


st.set_page_config(page_title="CustomerSupportAssist", page_icon="🛍️", layout="wide")

if "user" not in st.session_state:
    st.session_state.user = None
if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "history" not in st.session_state:
    st.session_state.history = []
if "pending_workflow" not in st.session_state:
    st.session_state.pending_workflow = None

if st.session_state.user is None:
    st.title("CustomerSupportAssist")
    st.caption("Internal support operations portal")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            try:
                user = login_support_user(username, password)
                st.session_state.user = user
                st.session_state.access_token = user.get("token")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    st.stop()

user = st.session_state.user
st.title(f"CustomerSupportAssist | {user['name']} ({user['role']})")
st.caption("E-commerce support operations dashboard")

if "history" not in st.session_state:
    st.session_state.history = []

with st.sidebar:
    st.header("Support controls")
    approved_action = st.toggle("Approval mode enabled", value=False, help="Allow risky actions like refund and return execution.")
    st.caption("Default policy: read-only mode unless explicitly approved.")

    st.markdown("---")
    st.subheader("Account")
    st.write(f"User: {user['name']}")
    st.write(f"Role: {user['role']}")
    if st.button("Logout"):
        st.session_state.user = None
        st.session_state.access_token = None
        st.rerun()

    st.markdown("---")
    st.subheader("Quick actions")
    st.button("Check order 10021")
    st.button("Get last 10 customer orders")
    st.button("Inventory risk summary")

query_examples = [
    "Look up order 10021 and show order total, payment status, and shipping status",
    "Show the last 5 orders for customer 457",
    "Check inventory for SKU-123 and tell me if stock is low",
    "What is the return rate over the last 30 days?",
    "Initiate a return for order 10021",
]

prompt = st.text_area("Ask a customer support question", value=query_examples[0], height=120)

metrics = [
    "total_revenue",
    "orders_count",
    "return_rate",
    "avg_order_value",
    "refund_resolution_time_days",
]

with st.container():
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.metric("Revenue (30d)", "$42.5K")
    with kpi2:
        st.metric("Orders", "1,284")
    with kpi3:
        st.metric("Return rate", "2.8%")
    with kpi4:
        st.metric("Inventory health", "94%")


tabs = st.tabs(["Operations", "Approval Center", "Metrics", "Audit Log"])

with tabs[0]:
    if st.button("Run support workflow"):
        with st.spinner("Analyzing support request..."):
            result = process_support_request(
                prompt,
                approved_action=approved_action,
                user_id=user.get("username"),
                session_id=st.session_state.get("access_token", "streamlit-session"),
            )

        response = result.get("response", {})
        st.session_state.pending_workflow = response.get("pending_state")
        st.subheader("Result")
        status = response.get("status")
        if status == "awaiting_follow_up":
            st.warning(response.get("answer"))
            missing = response.get("missing_fields", [])
            if missing:
                st.caption("Missing information: " + ", ".join(missing))
        elif status == "awaiting_human_approval":
            st.warning(response.get("answer"))
            if response.get("approval_request"):
                st.json(response["approval_request"])
        elif status in {"ok", "blocked"} and (response.get("rows") or response.get("presentation") or response.get("sql")):
            render_query_result(response)
        elif status == "action_completed":
            st.success(response.get("answer"))
        elif status == "no_action_needed":
            st.info(response.get("answer"))
        else:
            st.info(response.get("answer", "No result available."))

        if st.session_state.pending_workflow:
            pending = st.session_state.pending_workflow
            with st.form("workflow_follow_up"):
                st.caption("Complete the requested information to continue this workflow.")
                follow_up_answer = st.text_input("Your answer")
                resume_clicked = st.form_submit_button("Continue workflow")
                if resume_clicked:
                    if not follow_up_answer.strip():
                        st.error("Please provide the missing information.")
                    else:
                        resumed = resume_support_request(
                            follow_up_answer.strip(),
                            pending,
                            user_id=user.get("username"),
                            session_id=st.session_state.get("access_token", "streamlit-session"),
                        )
                        resumed_response = resumed.get("response", {})
                        st.session_state.pending_workflow = resumed_response.get("pending_state")
                        st.session_state.history.append({"prompt": follow_up_answer, "result": resumed})
                        st.success(resumed_response.get("answer", "Workflow updated."))
                        st.rerun()

        if result.get("trace"):
            st.subheader("Trace")
            st.json(result["trace"])

        st.session_state.history.append({"prompt": prompt, "result": result})

    if st.session_state.history:
        st.subheader("Recent interactions")
        for item in reversed(st.session_state.history[-5:]):
            st.markdown(f"**Q:** {item['prompt']}")
            st.json(item["result"].get("response", {}))

with tabs[1]:
    st.subheader("Create approval request")
    col1, col2 = st.columns(2)
    with col1:
        order_id = st.text_input("Order ID", "10021")
        action_type = st.selectbox("Action", ["refund_order", "create_return", "cancel_order", "update_inventory"])
    with col2:
        reason = st.text_input("Reason", "Damaged item received")
        requested_by = st.text_input("Requested by", user["username"])

    if st.button("Submit approval request"):
        payload = create_approval_request_for_ui(order_id, action_type, reason, requested_by)
        st.success(f"Approval request created: {payload['request_id']}")
        st.json(payload)

    st.markdown("---")
    st.subheader("Pending approvals")
    pending = list_pending_approvals_for_ui()
    if pending:
        pending_df = pd.DataFrame(pending)
        st.dataframe(pending_df, use_container_width=True)
        for _, row in pending_df.iterrows():
            with st.container():
                st.markdown(f"### {row['request_id']}")
                st.write(row.to_dict())
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    if st.button(f"Approve {row['request_id']}", key=f"approve-{row['request_id']}"):
                        approve_request_for_ui(row["request_id"], user["username"], "Approved by internal ops review")
                        st.success(f"Approved request {row['request_id']}")
                        st.rerun()
                with col_b:
                    if st.button(f"Reject {row['request_id']}", key=f"reject-{row['request_id']}"):
                        reject_request_for_ui(row["request_id"], user["username"], "Rejected by internal ops review")
                        st.warning(f"Rejected request {row['request_id']}")
                        st.rerun()
                with col_c:
                    if st.button(f"Cancel {row['request_id']}", key=f"cancel-{row['request_id']}"):
                        cancel_request_for_ui(row["request_id"], user["username"], "Cancelled by requestor or ops")
                        st.info(f"Cancelled request {row['request_id']}")
                        st.rerun()
    else:
        st.info("No pending approvals.")

    st.subheader("Approval history")
    history = list_all_approvals_for_ui()
    if history:
        st.dataframe(pd.DataFrame(history), use_container_width=True)

with tabs[2]:
    st.subheader("Semantic metrics")
    metric_name = st.selectbox("Metric", metrics)
    if st.button("Refresh metric"):
        from services.metrics_service import metric_lookup

        metric = metric_lookup(metric_name)
        st.json(metric)

    st.markdown("---")
    st.subheader("Analytics")
    data = {
        "Month": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
        "Revenue": [48, 52, 55, 60, 58, 62],
        "Returns": [5, 6, 7, 5, 4, 3],
        "Inventory Health": [88, 90, 92, 94, 93, 95],
    }
    df = pd.DataFrame(data)
    st.line_chart(df.set_index("Month")["Revenue"])
    st.bar_chart(df.set_index("Month")["Returns"])
    st.line_chart(df.set_index("Month")["Inventory Health"])

with tabs[3]:
    st.subheader("Audit trail")
    log_file = Path("logs/support_audit.jsonl")
    if log_file.exists():
        with log_file.open("r", encoding="utf-8") as handle:
            lines = [line.strip() for line in handle if line.strip()]
        events = [json.loads(line) for line in lines[-20:]]
        st.json(events)
    else:
        st.info("No audit log found yet.")

st.markdown("---")
st.markdown(
    """
    Supported workflows:
    - Order status and order history lookups
    - Customer support summaries
    - Inventory checks
    - Return and refund approval gates
    - DBT-style metric reporting
    """
)
