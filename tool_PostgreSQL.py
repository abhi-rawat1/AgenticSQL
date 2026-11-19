import psycopg
import pandas as pd
from sqlalchemy import create_engine, text
from langchain.tools import tool
import os
# postgresql+psycopg://USERNAME:PASSWORD@HOST:PORT/DATABASE


from dotenv import load_dotenv
load_dotenv()

DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_SCHEMA = os.getenv("DB_SCHEMA")
if not DB_PASSWORD or not DB_SCHEMA:
    raise ValueError("DB_PASSWORD or DB_SCHEMA is not set. Add them to your .env file.")

print(f"DB_PASSWORD: {DB_PASSWORD}")  # Debugging line to check if the password is loaded correctly
print(f"DB_SCHEMA: {DB_SCHEMA}")  # Debugging line to check if the schema is loaded correctly
engine = create_engine(
f"postgresql+psycopg://postgres:{DB_PASSWORD}@localhost:5432/postgres",
 connect_args={"options": f"-csearch_path={DB_SCHEMA}"}
)

@tool
def execute_query(query):
    """
    Use this tool to execute a SQL query and return the result as a pandas DataFrame.
    """
    print(f"Executing query: {query}")
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df.to_string(index=False) 

# create a function to get the schema of the database
@tool
def get_schema():
    """
    Use this tool to get the schema of the database as a dictionary.
    """
    with engine.connect() as conn:
        result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='aidemo';"))
        print(result)
        tables = [row[0] for row in result]
        schema = {}
        for table in tables:
            result = conn.execute(text(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name='{table}';"))
            columns = {row[0]: row[1] for row in result}
            schema[table] = columns
    return schema

# print(get_schema())   # Need to comment tool decorator to run this function directly

# print(execute_query("select count(*) from shipments;"))