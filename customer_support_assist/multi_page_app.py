import streamlit as st

from services.auth_service import authenticate_support_agent
from services.approval_service import list_all_approvals, list_pending_approvals

st.set_page_config(page_title="CustomerSupportAssist Ops", layout="wide")

if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            try:
                st.session_state.user = authenticate_support_agent(username, password)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    st.stop()

user = st.session_state.user
role = user["role"]

pages = {
    "Operations": "pages/operations.py",
    "Approval Center": "pages/approval_center.py",
    "Metrics": "pages/metrics.py",
    "Audit Log": "pages/audit_log.py",
}

# Access control: only allow pages by role
allowed = {
    "support_agent": ["Operations", "Approval Center", "Audit Log"],
    "operations_manager": ["Operations", "Approval Center", "Metrics", "Audit Log"],
    "finance_analyst": ["Metrics", "Audit Log"],
}

page_name = st.sidebar.selectbox("Navigate", [p for p in allowed.get(role, ["Operations"])])

if page_name == "Operations":
    st.title("Operations")
    st.info("Operations home page for order and support actions.")
    st.write("Pending approvals:", len(list_pending_approvals()))
elif page_name == "Approval Center":
    st.title("Approval Center")
    st.write(list_all_approvals())
elif page_name == "Metrics":
    st.title("Metrics")
    st.write("Revenue, return rate, inventory health")
elif page_name == "Audit Log":
    st.title("Audit Log")
    st.write("Audit history would appear here.")
