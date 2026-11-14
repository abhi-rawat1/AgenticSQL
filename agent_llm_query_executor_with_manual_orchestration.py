"""Manual orchestration example for a SQL-generation flow.

This script shows a simple two-step workflow: first ask the model to turn a user
request into PostgreSQL SQL, then run that SQL through the database tool.
"""

from langchain_openai import ChatOpenAI
from tool_PostgreSQL import execute_query, get_schema
from langchain_classic.schema import SystemMessage, HumanMessage, AIMessage
from langchain_classic.prompts import ChatPromptTemplate, MessagesPlaceholder

from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

# Find the list of model names at: https://platform.openai.com/docs/models
# The API key is expected to be loaded from the environment.

model = ChatOpenAI(model="gpt-6-luna")  # Create a model instance
schema = get_schema() # Need to comment tool decorator to run get_schema function directly

while True:
    user_input = input("Please enter your query (or type 'exit' to quit): ")
    if user_input.lower() == "exit":
        print("Exiting the program.")
        break

    # Build the message sent to the model, including the database schema.
    prompt = f"""You are a SQL Builder to execute a query in the PostgreSQL database and return the result as a pandas DataFrame. 
     input: {user_input}
     schema: {schema}
     """
    # Step 1: Ask the LLM to convert the natural-language request into SQL.
    response = model.invoke([HumanMessage(content=prompt)])
    response_content = response.content.replace("```sql", "").replace("```", "").strip()  # Clean up any code block formatting
    print("AI Response ********:", response_content)

    # Step 2: Execute the generated SQL against PostgreSQL.
    result = execute_query(response_content) # Need to comment tool decorator to run execute_query function directly
    print("Query Result:\n", result)

