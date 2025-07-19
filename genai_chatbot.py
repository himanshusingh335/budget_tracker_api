# budget_crew_ai.py

import sqlite3
import traceback
from crewai import Crew, Task, Agent, Process
from langchain_openai import ChatOpenAI
import os
from prompts import (
    QUESTION_PARSER_ROLE, QUESTION_PARSER_GOAL,
    SQL_VALIDATOR_ROLE, SQL_VALIDATOR_GOAL,
    QUERY_EXECUTOR_ROLE, QUERY_EXECUTOR_GOAL,
    ERROR_HANDLER_ROLE, ERROR_HANDLER_GOAL,
    ANSWER_SYNTHESIZER_ROLE, ANSWER_SYNTHESIZER_GOAL
)

DB_PATH = "data/budget.db"

os.environ["OPENAI_API_KEY"] = "dummy"

llm = ChatOpenAI(
    model="ollama/llama3.2",
    base_url="http://localhost:11434/v1",
    api_key="ollama",  # Required by langchain_openai even if dummy
    temperature=0
)

# Step 1: Agents
question_parser = Agent(
    role=QUESTION_PARSER_ROLE,
    goal=QUESTION_PARSER_GOAL,
    backstory="Expert in SQLite, familiar with financial data and schemas",
    llm=llm
)

sql_validator = Agent(
    role=SQL_VALIDATOR_ROLE,
    goal=SQL_VALIDATOR_GOAL,
    backstory="Knows the structure of budget_set and budget_tracker tables",
    llm=llm
)

query_executor = Agent(
    role=QUERY_EXECUTOR_ROLE,
    goal=QUERY_EXECUTOR_GOAL,
    backstory="Has access to database and returns result or error",
    is_llm=False,
    function=lambda sql: run_query(sql)
)

error_handler = Agent(
    role=ERROR_HANDLER_ROLE,
    goal=ERROR_HANDLER_GOAL,
    backstory="SQL troubleshooting expert with debugging skills",
    llm=llm
)

answer_synthesizer = Agent(
    role=ANSWER_SYNTHESIZER_ROLE,
    goal=ANSWER_SYNTHESIZER_GOAL,
    backstory="Expert in converting raw data into human language explanations",
    llm=llm
)

# Step 2: SQL Execution Helper
def run_query(sql_query: str):
    print(f"[DEBUG] Executing SQL Query: {sql_query}")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute(sql_query)
            rows = cur.fetchall()
            colnames = [description[0] for description in cur.description]
            print(f"[DEBUG] Query executed successfully. Columns: {colnames}, Rows: {rows}")
            return {"status": "success", "data": [dict(zip(colnames, row)) for row in rows]}
    except Exception as e:
        print(f"[DEBUG] Error executing query: {e}")
        return {"status": "error", "message": str(e), "query": sql_query}

# Step 3: Define Tasks
def get_tasks(user_question: str):
    print(f"[DEBUG] Creating tasks for user question: {user_question}")
    return [
        Task(
            description=f"Generate an SQL query from this question: '{user_question}'",
            agent=question_parser,
            expected_output="A valid SQLite SQL query string."
        ),
        Task(
            description="Validate this SQL query for correctness based on the schema",
            agent=sql_validator,
            expected_output="A validated/corrected SQLite SQL query string."
        ),
        Task(
            description="Execute the SQL query and return the output",
            agent=query_executor,
            expected_output="Query execution result as a list of rows or error details."
        ),
        Task(
            description="If there was an error in the SQL query, fix it and return the correct output",
            agent=error_handler,
            expected_output="A corrected SQLite SQL query string.",
            optional=True
        ),
        Task(
            description="Summarize the result into a human-friendly answer",
            agent=answer_synthesizer,
            expected_output="A human-friendly answer summarizing the query result."
        )
    ]

# Step 4: Crew
def run_budget_agent(user_question: str):
    print(f"[DEBUG] Running budget agent for question: {user_question}")
    crew = Crew(
        agents=[question_parser, sql_validator, query_executor, error_handler, answer_synthesizer],
        tasks=get_tasks(user_question),
        verbose=True,
        cache=True,
        process=Process.sequential,
        planning=False,
        planning_llm=llm
    )
    print("[DEBUG] Crew created, kicking off...")

    try:
        result = crew.kickoff()
        print(f"[DEBUG] Crew result: {result}")
        return result
    except Exception as e:
        print("[ERROR] Crew execution failed:")
        traceback.print_exc()
        return "[ERROR] Crew execution failed"

def test_llm():
    print("[DEBUG] Testing LLM with a simple prompt...")
    try:
        response = llm.invoke("Say hello!")
        print(f"[DEBUG] LLM response: {response}")
    except Exception as e:
        print(f"[DEBUG] LLM test failed: {e}")

# Uncomment to run the test
if __name__ == "__main__":
    #test_llm()
    #user_question = input("Enter your budget/spending question: ")
    user_question = "What was the total expenditure in June 2025?"
    answer = run_budget_agent(user_question)
    print("\n[RESULT]")
    print(answer)
