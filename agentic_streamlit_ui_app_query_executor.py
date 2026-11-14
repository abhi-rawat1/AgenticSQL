"""Streamlit chat UI for a SQL-building LangChain agent.

This app sends the user's request to an agent that can inspect the database
schema and run SQL queries through PostgreSQL tools. It also surfaces the
intermediate tool calls so the user can see how the agent reached the answer.


Prompt to generqate the Streamlit UI for the SQL-building LangChain agent. 

The app sends the user's request to an agent that can inspect the database schema and run SQL queries through PostgreSQL tools. 
It also surfaces the intermediate tool calls so the user can see how the agent reached the answer.

Use agentic_sys_query_executor_with_tracer.py file & create a UI application using streamlit that should have folowing features-

a. Allow user to provide the user input and then display the response in form of chat
b. dont edit existing file.. instead create a new file
c. have a history option
d. also have an option to see the list of tools which were called for each req

"""

import json
from typing import Any, Dict, List

import streamlit as st
from dotenv import load_dotenv
from langchain.agents import  create_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from tool_PostgreSQL import execute_query, get_schema

load_dotenv()

TOOLS = [execute_query, get_schema]

def extract_tool_calls(messages: List[Any]) -> List[Dict[str, Any]]:
    """Extract tool calls from AI messages and pair them with later tool outputs."""
    tool_calls: List[Dict[str, Any]] = []
    pending: List[Dict[str, Any]] = []

    for message in messages or []:
        # 1) AI message with tool_calls
        ai_tool_calls = None
        if hasattr(message, "tool_calls") and getattr(message, "tool_calls"):
            ai_tool_calls = getattr(message, "tool_calls")
        elif hasattr(message, "additional_kwargs") and isinstance(message.additional_kwargs, dict):
            ai_tool_calls = message.additional_kwargs.get("tool_calls")

        if ai_tool_calls:
            for tool_call in ai_tool_calls:
                if isinstance(tool_call, dict):
                    fn = tool_call.get("function") or {}
                    name = tool_call.get("name") or fn.get("name")
                    raw_args = tool_call.get("args") or fn.get("arguments", {})
                    if isinstance(raw_args, str):
                        try:
                            raw_args = json.loads(raw_args)
                        except json.JSONDecodeError:
                            raw_args = {"raw": raw_args}
                    call_id = tool_call.get("id")
                    pending.append(
                        {
                            "id": call_id,
                            "tool": name,
                            "input": raw_args or {},
                            "output": None,
                        }
                    )

        # 2) Tool result message
        if getattr(message, "type", None) == "tool" or hasattr(message, "tool_call_id"):
            tool_call_id = getattr(message, "tool_call_id", None)
            tool_name = getattr(message, "name", None)
            output = getattr(message, "content", None)

            for call in pending:
                if call["id"] == tool_call_id:
                    call["tool"] = call.get("tool") or tool_name
                    call["output"] = output
                    break
            else:
                tool_calls.append(
                    {
                        "tool": tool_name,
                        "input": {},
                        "output": output,
                    }
                )

    # 3) Add any matched tool calls in the order they were seen
    for call in pending:
        if call.get("tool") is not None:
            tool_calls.append(
                {
                    "tool": call.get("tool"),
                    "input": call.get("input", {}),
                    "output": call.get("output"),
                }
            )

    return tool_calls

if "agent" not in st.session_state:
    llm_model = ChatOpenAI(model="gpt-6-luna")
    st.session_state.agent= create_agent(
        llm_model,
        tools=TOOLS,
        system_prompt="You are a SQL Builder and use tools to execute a query and return the result as a pandas DataFrame.",
    )
    #st.session_state.agent = build_agent()

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

st.set_page_config(page_title="SQL Agent UI", page_icon="🧠")
st.title("SQL Agent Chat Assistant")

with st.sidebar:
    st.header("Options")
    show_history = st.checkbox("Show conversation history", value=True)
    if st.button("Clear chat history"):
        st.session_state.chat_history = []

    st.subheader("Available tools")
    for tool in TOOLS:
        st.markdown(f"- {tool.name}")

user_input = st.chat_input("Ask a question or request a database query...")

if user_input:
    with st.spinner("Processing your request..."):
        response = st.session_state.agent.invoke({'messages': [user_input]})
        print(response)
        print("********")
        answer = response['messages'][-1].text or "No answer was returned."
        tool_calls = extract_tool_calls(response.get("messages", []))
        print("Extracted tool calls:", tool_calls)

    st.session_state.chat_history.append(
        {
            "question": user_input,
            "answer": answer,
            "tools": tool_calls,
        }
    )

    st.rerun()

if show_history:
    for idx, item in enumerate(st.session_state.chat_history):
        st.markdown(f"### Request {idx + 1}")
        with st.chat_message("user"):
            st.write(item["question"])

        with st.chat_message("assistant"):
            st.write(item["answer"])

        with st.expander("View tool calls used for this request"):
            if item["tools"]:
                for tool_info in item["tools"]:
                    st.markdown(f"**Tool:** {tool_info.get('tool', 'Unknown')}")
                    st.markdown("**Input:**")
                    st.code(json.dumps(tool_info.get("input", {}), default=str, indent=2))
                    st.markdown("**Output:**")
                    st.code(str(tool_info.get("output", "")))
            else:
                st.info("No tool was called for this request.")
else:
    if st.session_state.chat_history:
        latest = st.session_state.chat_history[-1]
        with st.chat_message("user"):
            st.write(latest["question"])

        with st.chat_message("assistant"):
            st.write(latest["answer"])

        with st.expander("View tool calls used for this request"):
            if latest["tools"]:
                for tool_info in latest["tools"]:
                    st.markdown(f"**Tool:** {tool_info.get('tool', 'Unknown')}")
                    st.markdown("**Input:**")
                    st.code(json.dumps(tool_info.get("input", {}), default=str, indent=2))
                    st.markdown("**Output:**")
                    st.code(str(tool_info.get("output", "")))
            else:
                st.info("No tool was called for this request.")
    else:
        st.info("Ask your first question to start the chat.")
