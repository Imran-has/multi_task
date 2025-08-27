import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
from agents import Agent, ModelSettings, function_tool, Runner
import asyncio
from config.config import model

# Define math function
@function_tool
async def add(a: int, b: int) -> int:
    """Return the sum of two numbers"""
    return a + b

# Create Math Agent
math_agent = Agent(
    name="MathAgent",
    instructions="You are a math expert. You will be given two numbers and you must return their sum.",
    model=model,
    tools=[add],
    model_settings=ModelSettings(max_retries=2)
)

math_tool = math_agent.as_tool(
    tool_name="math_tool",
    tool_description="Solve addition questions."
)
# Main function with 3 test questions
async def main():
    questions = [
        "What is the sum of 5 and 7?",
        "Add 10 and 15.",
        "Give me the addition of 23 and 77."
    ]

    for q in questions:
        result = await Runner.run(math_agent, q)
        print(f"Q: {q}\nAnswer: {result.final_output}\n")

if __name__ == "__main__":
    asyncio.run(main())
