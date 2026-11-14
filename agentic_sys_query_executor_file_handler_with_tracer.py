"""SQL agent with tracing and file-system tooling.

This script extends the database agent with file operations so the model can
read and modify project files while still logging the full message and tool
execution trail for debugging.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult
from langchain_openai import ChatOpenAI

from tool_PostgreSQL import execute_query, get_schema
from tool_fileHandling import read_file, write_file, list_files, run_command, edit_file

load_dotenv()

tools = [execute_query, get_schema, read_file, write_file, list_files, run_command, edit_file]
TRACE_LOG = Path(__file__).with_name("agent_traces_log.json")


def _json_default(value: Any) -> str:
    """Return a JSON-serializable string for UUID and other non-JSON objects."""
    if isinstance(value, UUID):
        return str(value)
    return str(value)


def message_to_record(message: BaseMessage | Any) -> dict[str, Any]:
    """Normalize a LangChain message into a plain dictionary for tracing."""
    if isinstance(message, BaseMessage):
        data = message.model_dump()
        return {
            "role": data.get("type") or message.__class__.__name__,
            "content": data.get("content"),
            "tool_calls": data.get("tool_calls") or None,
            "name": data.get("name"),
            "tool_call_id": data.get("tool_call_id"),
        }
    return {"role": type(message).__name__, "content": str(message)}


class AgentTraceHandler(BaseCallbackHandler):
    """Records every payload sent to the chat model and every tool call."""

    def __init__(self) -> None:
        self.llm_turns: list[dict[str, Any]] = []
        self.tool_calls: list[dict[str, Any]] = []
        self._pending_tools: dict[str, dict[str, Any]] = {}

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[BaseMessage]],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        print(f"************on_chat_model_start ***********: run_id={run_id}, parent_run_id={parent_run_id}, tags={tags}, metadata={metadata}")
        print(f"Messages: {messages}")
        batches = [[message_to_record(message) for message in batch] for batch in messages]
        self.llm_turns.append(
            {
                "run_id": str(run_id),
                "model": (serialized or {}).get("name") or (serialized or {}).get("id"),
                "messages_sent_to_model": batches[0] if len(batches) == 1 else batches,
                "model_response": None,
            }
        )

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        replies: list[dict[str, Any]] = []
        print(f"************on_llm_end ***********: run_id={run_id}, parent_run_id={parent_run_id}, tags={tags}")
        print(f"Response: {response}")
        for generation_list in response.generations:
            for generation in generation_list:
                message = getattr(generation, "message", None)
                if message is not None:
                    replies.append(message_to_record(message))
                else:
                    replies.append({"role": "ai", "content": generation.text})

        record = next((turn for turn in self.llm_turns if turn["run_id"] == str(run_id)), None)
        payload = replies[0] if len(replies) == 1 else replies
        if record is None:
            self.llm_turns.append(
                {
                    "run_id": str(run_id),
                    "model": None,
                    "messages_sent_to_model": [],
                    "model_response": payload,
                }
            )
        else:
            record["model_response"] = payload

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        print(f"************on_tool_start ***********: run_id={run_id}, parent_run_id={parent_run_id}, tags={tags}, metadata={metadata}")
        print(f"Tool input: {json.dumps(inputs if inputs is not None else input_str, default=_json_default)}")
        print(f"Tool inputs string : {input_str}")
        self._pending_tools[str(run_id)] = {
            "run_id": str(run_id),
            "tool": (serialized or {}).get("name"),
            "input": inputs if inputs is not None else input_str,
            "output": None,
            "error": None,
        }

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        print(f"************on_tool_end ***********: run_id={run_id}, parent_run_id={parent_run_id}, tags={tags}")
        print(f"Tool output: {output}")
        record = self._pending_tools.pop(str(run_id), {"run_id": str(run_id), "tool": None, "input": None})
        record["output"] = getattr(output, "content", output)
        self.tool_calls.append(record)

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        print(f"************on_tool_error ***********: run_id={run_id}, parent_run_id={parent_run_id}, tags={tags}")
        record = self._pending_tools.pop(str(run_id), {"run_id": str(run_id), "tool": None, "input": None})
        record["error"] = f"{type(error).__name__}: {error}"
        self.tool_calls.append(record)

    def snapshot(self, user_input: str, final_answer: str) -> dict[str, Any]:
        """Save the full conversation summary for one agent run."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_input": user_input,
            "llm_turns": self.llm_turns,
            "tool_calls": self.tool_calls,
            "final_answer": final_answer,
        }


def print_trace(trace: dict[str, Any]) -> None:
    """Print the LLM turns and tool calls in a readable debugging format."""
    print("\n========== Agent trace ==========")
    for index, turn in enumerate(trace["llm_turns"], start=1):
        print(f"\n--- LLM turn {index}: messages sent to the model ---")
        sent = turn["messages_sent_to_model"]
        batches = sent if sent and isinstance(sent[0], list) else [sent]
        for batch in batches:
            for message in batch:
                print(f"[{message.get('role')}] {message.get('content')}")
                if message.get("tool_calls"):
                    print(f"  tool_calls: {json.dumps(message['tool_calls'], default=_json_default)}")
                if message.get("name") or message.get("tool_call_id"):
                    print(f"  name={message.get('name')} tool_call_id={message.get('tool_call_id')}")
        print(f"--- LLM turn {index}: model response ---")
        response = turn["model_response"]
        responses = response if isinstance(response, list) else [response]
        for message in responses:
            if not message:
                print("(no response captured)")
                continue
            print(f"[{message.get('role')}] {message.get('content')}")
            if message.get("tool_calls"):
                print(f"  tool_calls: {json.dumps(message['tool_calls'], default=_json_default)}")

    print("\n--- Tool calls ---")
    if not trace["tool_calls"]:
        print("No tools were called.")
    for index, call in enumerate(trace["tool_calls"], start=1):
        print(f"\nTool {index}: {call.get('tool')}")
        print(f"Input: {json.dumps(call.get('input'), default=_json_default)}")
        if call.get("error"):
            print(f"Error: {call['error']}")
        else:
            print(f"Output: {call.get('output')}")
    print("========== End trace ==========\n")


def save_trace(trace: dict[str, Any]) -> None:
    """Store the trace in JSON lines so every agent run remains inspectable."""
    with TRACE_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(trace, default=_json_default) + "\n")


def main() -> None:
    """Run the agent in a loop, capturing LLM payloads and tool activity."""
    llm_model = ChatOpenAI(model="gpt-6-luna")
    agent = create_agent(
        llm_model,
        tools=tools,
        system_prompt="You are a SQL Builder and use tools to execute a query and return the result as a pandas DataFrame.",
    )

    while True:
        user_input = input("Please enter your query (or type 'exit' to quit): ")
        if user_input.lower() == "exit":
            print("Exiting the program.")
            break
        print("=================== LLM Processing Start ====================================")
        tracer = AgentTraceHandler()
        response = agent.invoke(
            {"messages": [user_input]},
            config={"callbacks": [tracer]},
        )
        final_answer = response["messages"][-1].text
        print("=================== LLM Processing End ====================================")
        print("=================== Trace captured and printing to console ===================")
        trace = tracer.snapshot(user_input, final_answer)
        print("trace:", json.dumps(trace, default=_json_default, indent=2))
        print_trace(trace)
        save_trace(trace)
        print("========== Model Final Response ==========")
        
        print(final_answer)


if __name__ == "__main__":
    main()
