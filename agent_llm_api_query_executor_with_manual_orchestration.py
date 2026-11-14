"""Manual orchestration example via LLM API for a SQL-generation & executionflow.

This script shows a simple two-step workflow: first ask the model to turn a user
request into PostgreSQL SQL, then run that SQL through the database tool.

The agent loop: the part that turns a chat model into an agent.

ask the model -> it wants tools? -> run them, show it the results -> ask again
                  -> it just answers? -> done

Before running, 
--> set the environment variable OPENAI_API_KEY to your OpenAI API key, or set GROQ_API_KEY to your Groq API key, or set NVIDIA_API_KEY to your NVIDIA API key.
--> Comment out the @tool decorator in tool_PostgreSQL.py and tool_fileHandling.py to run the functions directly.

Run it:   python agent_llm_api_query_executor_with_manual_orchestration.py                  (chat)
          python agent_llm_api_query_executor_with_manual_orchestration.py "make hello.py"  (one task, then exit)
"""

from langchain_openai import ChatOpenAI
from tool_PostgreSQL import execute_query, get_schema
from langchain_classic.schema import SystemMessage, HumanMessage, AIMessage
from langchain_classic.prompts import ChatPromptTemplate, MessagesPlaceholder

from tool_fileHandling import read_file, write_file, list_files, run_command, edit_file

from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

import json
import os
import platform
import sys

import gateway


MAX_STEPS = 25  # a safety net so a confused model can't loop forever

SYSTEM_PROMPT = """You are mini-claude, a small coding agent.
You work in this folder: {workdir}  (operating system: {os})
For files outside it, just call the tool: the user will be asked for permission.
Look at files before you change them. After changing code, run it to check it works.
When you run something, include its actual output in your reply.
If a tool result says BLOCKED, don't try to get around it; tell the user why.
Keep your replies short.

Permission mode right now: {mode}
(read-only: only reading. ask: the user approves each write or command. auto: no approval needed.)
The mode can change during the chat, so always call the tool and let the harness
decide. Never refuse on your own because of something that was blocked earlier.
"""

MODE='ask'
HERE = os.path.dirname(os.path.abspath(__file__))
WORKDIR = os.path.realpath(os.environ.get("WORKDIR") or os.path.join(HERE, "workspace"))


# name -> (function, what it does, {argument: what it means})
TOOLS = {
    "read_file":   (read_file, "Read a text file.",
                    {"path": "File path, relative to the project"}),
    "write_file":  (write_file, "Create a file, or overwrite it completely.",
                    {"path": "File path, relative to the project",
                     "content": "The full content of the file"}),
    "edit_file":   (edit_file, "Replace one exact snippet of text in a file.",
                    {"path": "File path, relative to the project",
                     "old": "The exact text to find (must appear once)",
                     "new": "The text to put in its place"}),
    "list_files":  (list_files, "List every file under a folder.",
                    {"path": "Folder path; use . for the project root"}),
    "run_command": (run_command, "Run a shell command in the project folder (60s limit).",
                    {"command": "The command to run"}),
    "execute_query": (execute_query, "Execute a SQL query and return the result as a pandas DataFrame.",
                    {"query": "The SQL query to execute"}),
    "get_schema": (get_schema, "Get the schema of the PostgreSQL database.",
                    {})
}


def schemas():
    """Describe every tool in the JSON shape the OpenAI format expects."""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": {arg: {"type": "string", "description": meaning}
                                   for arg, meaning in arguments.items()},
                    "required": list(arguments),
                },
            },
        }
        for name, (_, description, arguments) in TOOLS.items()
    ]

def system_prompt():
    """Rebuilt before every task, so the model always sees the current mode and memory."""
    return SYSTEM_PROMPT.format(workdir=WORKDIR, os=platform.system(), mode=MODE)

def run_tool(call):
    """Run one tool call and return its result as text. Errors are results too:
    the model reads them and tries something else, instead of us crashing."""
    name = call["function"]["name"]
    try:
        args = json.loads(call["function"]["arguments"])
    except json.JSONDecodeError:
        return "ERROR: the arguments were not valid JSON"
    print(f"  [{name}] {json.dumps(args)[:100]}")

    if name not in TOOLS:
        return f"ERROR: there is no tool called {name}"
    
    '''
    reason = hooks.run_before(name, args) or guardrails.check(name, args)
    if reason:
        print(f"  BLOCKED: {reason}")
        return f"BLOCKED: {reason}"
    '''

    function = TOOLS[name][0]
    print(f"  [***** running tool function {name}...] ")
    try:
        result = function(**args)
        print(f"  [***** tool {name} returned] {str(result)[:100]} ")
    except Exception as error:
        result = f"ERROR: {type(error).__name__}: {error}"
    # hooks.run_after(name, args, result)
    
    if name == "run_command":  # show what the command printed, not just that it ran
        print("\n".join(f"    | {line}" for line in str(result).splitlines()[:20]))
    return result


def agent_loop(messages):
    """Keep calling the model until it answers without asking for a tool."""
    for _ in range(MAX_STEPS):
        # context.trim_results(messages)  # a long task can outgrow the budget too
        print(f"  [***** sending message ] {messages} ")
        reply = gateway.chat(messages, schemas())
        print(f"  [***** model reply] {reply} ")
        messages.append(reply)

        if not reply.get("tool_calls"):
            return reply["content"]
        if reply["content"]:
            print(f"  {reply['content']}")

        for call in reply["tool_calls"]:
            print(f"  [***** tool call] {call} ")
            result = run_tool(call)
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": str(result)})
    return f"(stopped after {MAX_STEPS} steps)"

def ask(messages, task):
    """Run one task. If it fails halfway, undo it so the conversation stays valid."""
    messages[0] = {"role": "system", "content": system_prompt()}
    # context.compact(messages)  # squeeze old turns if we're over the context budget
    checkpoint = len(messages)
    messages.append({"role": "user", "content": task})
    try:
        return agent_loop(messages)
    except KeyboardInterrupt:
        del messages[checkpoint:]
        return "(interrupted)"
    except Exception as error:
        del messages[checkpoint:]
        return f"(error: {error})"

def main():
    os.makedirs(WORKDIR, exist_ok=True)
    messages = [{"role": "system", "content": system_prompt()}]

    if len(sys.argv) > 1:  # one task from the command line, then exit
        print(ask(messages, " ".join(sys.argv[1:])))
        return

    while True:
        try:
            user_input = input("Please enter your query (or type 'exit' to quit): ")
    
            if user_input.lower() in ("exit", "quit"):
                print("Exiting the program.")
                break
            
            response = ask(messages, user_input)

        except (EOFError, KeyboardInterrupt):
            break

if __name__ == "__main__":
    main()

