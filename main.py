import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from my_agent.hostel_information import guardrial_agent
import asyncio

from agents import Runner

async def main():
    result = await Runner.run(    guardrial_agent,
    "What are the check-in policies for Hotel Sannata?",
    context={"user_id": "12345"})
    print(result)

if __name__ == "__main__":
    asyncio.run(main())