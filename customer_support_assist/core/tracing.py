import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import settings

LOG_PATH = Path(settings.log_dir) / "support_audit.jsonl"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def write_audit_event(event_type: str, payload: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "request_id": request_id or "unknown",
        "payload": payload,
    }
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, default=str) + "\n")
    return event


def trace_request_step(step_name: str, request_id: str, details: dict[str, Any]) -> dict[str, Any]:
    return write_audit_event(step_name, details, request_id=request_id)
