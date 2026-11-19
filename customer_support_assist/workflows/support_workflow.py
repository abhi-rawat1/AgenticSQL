from __future__ import annotations

import uuid
from typing import Any

from core.tracing import trace_request_step
from services.sql_agent import build_sql_agent, classify_support_intent, validate_support_request


def process_support_request(user_message: str, approved_action: bool = False) -> dict[str, Any]:
    request_id = str(uuid.uuid4())
    trace_request_step("request_received", request_id, {"user_message": user_message})

    validation = validate_support_request(user_message, approved_action=approved_action)
    trace_request_step("intent_validation", request_id, validation)

    if not validation["allowed"]:
        return {
            "response": {
                "status": "blocked",
                "message": validation["reason"],
                "required_action": validation["action"],
                "approval_required": True,
            },
            "trace": [
                {"event": "request_received", "request_id": request_id, "payload": {"user_message": user_message}},
                {"event": "intent_validation", "request_id": request_id, "payload": validation},
            ],
        }

    intent = classify_support_intent(user_message)
    trace_request_step("intent_detected", request_id, {"intent": intent})

    agent = build_sql_agent()
    response = agent.invoke({"input": user_message, "chat_history": []})
    final_answer = response.get("output", "I could not process that request.")

    trace_request_step("final_response", request_id, {"answer": final_answer})

    return {
        "response": {
            "status": "ok",
            "intent": intent,
            "answer": final_answer,
        },
        "trace": [
            {"event": "request_received", "request_id": request_id, "payload": {"user_message": user_message}},
            {"event": "intent_validation", "request_id": request_id, "payload": validation},
            {"event": "intent_detected", "request_id": request_id, "payload": {"intent": intent}},
            {"event": "final_response", "request_id": request_id, "payload": {"answer": final_answer}},
        ],
    }
