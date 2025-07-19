from crewai import Crew, Agent, Task
from langchain_openai import ChatOpenAI
import os

os.environ["OPENAI_API_KEY"] = "dummy"

llm = ChatOpenAI(model="ollama/llama3.2", base_url="http://localhost:11434", temperature=0)

# Define a simple agent
test_agent = Agent(
    role="Test Assistant",
    goal="Answer simple questions using Llama 3.2 via Ollama.",
    backstory="A helpful assistant for basic queries.",
    llm=llm
)

# Define a simple task
test_task = Task(
    description="Say hello and introduce yourself.",
    agent=test_agent,
    expected_output="A friendly greeting and introduction."
)

# Run the Crew
if __name__ == "__main__":
    crew = Crew(
        agents=[test_agent],
        tasks=[test_task],
        verbose=True
    )
    result = crew.kickoff()
    print("\n[RESULT]")
    print(result)
