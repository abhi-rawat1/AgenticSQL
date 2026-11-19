from __future__ import annotations

import uuid
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from core.guardrails import detect_support_intent
from core.tracing import (
    flush_langfuse,
    get_langfuse_langchain_handler,
    langfuse_workflow_trace,
    trace_request_step,
)
from services.approval_service import create_approval_request
from services.sql_agent import build_sql_agent


class SupportWorkflowState(TypedDict, total=False):
    user_message: str
    request_id: str
    approved_action: bool
    intent: str
    confidence: float
    entities: dict[str, Any]
    missing_fields: list[str]
    follow_up_question: str | None
    status: str
    answer: str
    approval_request: dict[str, Any] | None
    trace: list[dict[str, Any]]


_ACTION_TYPES = {
    "initiate_refund": "refund_order",
    "cancel_item": "cancel_order",
    "cancel_order": "cancel_order",
    "initiate_return": "create_return",
}

_REQUIRED_FIELDS = {
    "initiate_refund": ("order_id", "reason"),
    "cancel_item": ("order_id",),
    "cancel_order": ("order_id",),
    "initiate_return": ("order_id", "reason"),
    "refund_status": ("order_id", "refund_id"),
}


def _required_missing(intent: str, entities: dict[str, Any]) -> list[str]:
    required = _REQUIRED_FIELDS.get(intent, ())
    if intent == "refund_status":
        if entities.get("order_id") or entities.get("refund_id"):
            return []
        return ["order_id or refund_id"]
    missing: list[str] = []
    for field in required:
        if not entities.get(field):
            missing.append(field)
    return missing


def _intent_node(state: SupportWorkflowState) -> SupportWorkflowState:
    request_id = state["request_id"]
    trace_request_step("request_received", request_id, {"user_message": state["user_message"]})
    print(f"In the intent node *** : {state}")
    decision = detect_support_intent(state["user_message"])
    print(f"Intent decision ** : {decision}")
    entities = decision.entities or {}
    missing = _required_missing(decision.intent, entities)

    payload = decision.model_dump()
    trace_request_step("llm_intent_detected", request_id, payload)

    return {
        **state,
        "intent": decision.intent,
        "confidence": decision.confidence,
        "entities": entities,
        "missing_fields": missing,
        "follow_up_question": decision.follow_up_question,
        "status": "classified",
    }


def _route_node(state: SupportWorkflowState) -> str:
    intent = state.get("intent", "unknown")
    if state.get("missing_fields"):
        return "awaiting_follow_up"
    if intent in _ACTION_TYPES:
        return "human_approval"
    if intent in {"refund_status", "general_query", "lookup_order", "lookup_customer_orders", "inventory_check", "metric_query"}:
        return "read_query"
    return "clarification"


def _read_query_node(state: SupportWorkflowState) -> SupportWorkflowState:
    request_id = state["request_id"]
    agent = build_sql_agent()
    handler = get_langfuse_langchain_handler()
    invoke_config = {"callbacks": [handler]} if handler is not None else None

    trace_request_step("read_query_started", request_id, {"intent": state["intent"]})
    if invoke_config:
        response = agent.invoke({"input": state["user_message"], "chat_history": []}, config=invoke_config)
    else:
        response = agent.invoke({"input": state["user_message"], "chat_history": []})
    answer = response.get("output", "I could not process that request.")

    trace_request_step("final_response", request_id, {"answer": answer})
    return {**state, "status": "ok", "answer": answer, "approval_request": None}


def _human_approval_node(state: SupportWorkflowState) -> SupportWorkflowState:
    request_id = state["request_id"]
    intent = state["intent"]
    entities = state.get("entities", {})
    action_type = _ACTION_TYPES[intent]
    order_id = str(entities.get("order_id") or entities.get("item_id") or "unknown")
    reason = str(entities.get("reason") or entities.get("return_reason") or f"Human approval requested for {intent}")

    approval = create_approval_request(
        order_id=order_id,
        action_type=action_type,
        reason=reason,
        requested_by="support-agent",
    )
    trace_request_step(
        "human_approval_requested",
        request_id,
        {"intent": intent, "request_id": approval["request_id"]},
    )
    return {
        **state,
        "status": "awaiting_human_approval",
        "answer": "This action requires human approval before execution.",
        "approval_request": approval,
    }


def _follow_up_node(state: SupportWorkflowState) -> SupportWorkflowState:
    request_id = state["request_id"]
    missing = state.get("missing_fields", [])
    question = state.get("follow_up_question")
    if not question:
        question = "Please provide the missing information: " + ", ".join(missing) + "."
    trace_request_step("follow_up_required", request_id, {"missing_fields": missing, "question": question})
    return {
        **state,
        "status": "awaiting_follow_up",
        "answer": question,
        "approval_request": None,
    }


def _clarification_node(state: SupportWorkflowState) -> SupportWorkflowState:
    request_id = state["request_id"]
    answer = state.get("follow_up_question") or "Please clarify whether you need an order lookup or want to initiate a refund, return, or cancellation."
    trace_request_step("clarification_required", request_id, {"intent": state.get("intent")})
    return {**state, "status": "awaiting_clarification", "answer": answer, "approval_request": None}


def build_support_workflow():
    graph = StateGraph(SupportWorkflowState)
    graph.add_node("intent", _intent_node)
    graph.add_node("read_query", _read_query_node)
    graph.add_node("human_approval", _human_approval_node)
    graph.add_node("awaiting_follow_up", _follow_up_node)
    graph.add_node("clarification", _clarification_node)

    graph.set_entry_point("intent")
    graph.add_conditional_edges(
        "intent",
        _route_node,
        {
            "read_query": "read_query",
            "human_approval": "human_approval",
            "awaiting_follow_up": "awaiting_follow_up",
            "clarification": "clarification",
        },
    )
    graph.add_edge("read_query", END)
    graph.add_edge("human_approval", END)
    graph.add_edge("awaiting_follow_up", END)
    graph.add_edge("clarification", END)
    return graph.compile()


_support_workflow = build_support_workflow()


def process_support_request(
    user_message: str,
    approved_action: bool = False,
    user_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    request_id = str(uuid.uuid4())
    initial_state: SupportWorkflowState = {
        "user_message": user_message,
        "request_id": request_id,
        "approved_action": approved_action,
        "entities": {},
        "missing_fields": [],
        "trace": [],
    }
    trace_request_step(
        "workflow_started",
        request_id,
        {"user_id": user_id, "session_id": session_id, "user_message": user_message},
    )

    with langfuse_workflow_trace(
        name="support-workflow-turn",
        input_payload={"user_message": user_message},
        request_id=request_id,
        user_id=user_id,
        session_id=session_id,
    ) as root_span:
        final_state = _support_workflow.invoke(initial_state)
        trace_request_step("workflow_completed", request_id, {"status": final_state["status"]})
        if root_span is not None:
            root_span.update(
                input={"user_message": user_message},
                output={"status": final_state["status"], "answer": final_state.get("answer")},
                metadata={
                    "intent": final_state.get("intent"),
                    "confidence": final_state.get("confidence"),
                    "request_id": request_id,
                },
            )

    flush_langfuse()

    return {
        "response": {
            "status": final_state["status"],
            "intent": final_state.get("intent"),
            "confidence": final_state.get("confidence"),
            "answer": final_state.get("answer"),
            "missing_fields": final_state.get("missing_fields", []),
            "approval_request": final_state.get("approval_request"),
        },
        "trace": [
            {"event": "workflow_completed", "request_id": request_id, "payload": {"status": final_state["status"]}},
        ],
    }
