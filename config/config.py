from agents import  AsyncOpenAI, OpenAIChatCompletionsModel, RunConfig
# 
import os
from dotenv import load_dotenv

# Load .env environment variables if needed
load_dotenv()

# Load Gemini API Key from environment
gemini_api_key = os.getenv("GEMINI_API_KEY")

# Validate API key
if not gemini_api_key:
    raise ValueError("GEMINI_API_KEY not found in environment variables.")

# Reference: https://ai.google.dev/gemini-api/docs/openai
external_client = AsyncOpenAI(
    api_key=gemini_api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

model = OpenAIChatCompletionsModel(
    model="gemini-2.0-flash",
    openai_client=external_client
)

config = RunConfig(
    model=model,
    model_provider=external_client,
    tracing_disabled=True
)

