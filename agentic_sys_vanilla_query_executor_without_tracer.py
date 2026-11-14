"""Minimal command-line agent for SQL queries without runtime tracing.

This version keeps the setup simple: it creates a LangChain tool-calling agent,
attaches the PostgreSQL tools, and waits for user requests in a loop.
"""

from typing import Callable, Dict, List, Optional, Any
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from tool_PostgreSQL import execute_query, get_schema

from dotenv import load_dotenv
load_dotenv()

tools = [execute_query, get_schema]

def build_langchain_agent(
    model_name: str = "gpt-6-luna",
    system_prompt: str = "You are a SQL Builder and use tools to execute a query and return the result as a pandas DataFrame.",
    tools: Optional[List[Any]] = None,) -> AgentExecutor:
    """Create the LangChain SQL agent and attach the available database tools."""
    llm = ChatOpenAI(model=model_name)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )

    agent_tools = tools or []
    agent = create_tool_calling_agent(llm, agent_tools, prompt)
    return AgentExecutor(agent=agent, tools=agent_tools, verbose=True)


def main() -> None:
    """Run the interactive loop and send each user question to the SQL agent."""
    agent = build_langchain_agent(model_name="gpt-6-luna", tools=tools)
    while True:
        user_input = input("Please enter your query (or type 'exit' to quit): ")
        if user_input.lower() == "exit":
            print("Exiting the program.")
            break
        print("=================== LLM Processing Start ====================================")
        response = agent.invoke({"input": user_input})
        print(f"Response: {response}")

if __name__ == "__main__":
    main()