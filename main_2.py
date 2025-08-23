import asyncio
import os
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from agents import Agent, ModelSettings, set_tracking_disabled, function_tool, guardrail
from config.config import model
from agents import AsyncOpenAI, OpenAIChatCompletionsModel, RunConfig
# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="support_bot.log"
)
logger = logging.getLogger(__name__)

# Environment variables load karo
load_dotenv()
gemini_api_key = os.getenv("GEMINI_API_KEY")
if not gemini_api_key:
    raise ValueError("GEMINI_API_KEY environment mein nahi mila.")

# AsyncOpenAI client aur model

external_client = AsyncOpenAI(
    api_key=gemini_api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)
model = OpenAIChatCompletionsModel(
    model="gemini-2.0-flash",
    openai_client=external_client
)

# Fake order database
ORDERS_DB = {
    "ORD123": "Shipped - Expected delivery in 3 days",
    "ORD456": "Processing - Will ship soon",
    "ORD789": "Delivered - Thank you for shopping!"
}

# FAQ database
FAQS = {
    "return policy": "Hamari return policy 30 din ke andar wapas karne ki ijazat deti hai agar receipt ho.",
    "shipping time": "Standard shipping mein 3-5 business days lagte hain.",
    "contact support": "Mazeed madad ke liye hamari human support team se rabta karen."
}

# Function tool for order status (error_function ke bina)
@function_tool(
    is_enabled=lambda query, **kwargs: "order" in query.lower()
)
async def get_order_status(order_id: str) -> str:
    """
    Fake database se order status fetch karo.
    """
    logger.info(f"Order status fetch kar raha hoon for order_id: {order_id}")
    status = ORDERS_DB.get(order_id)
    if status:
        return f"Order {order_id} ka status: {status}"
    else:
        logger.warning(f"Order ID {order_id} nahi mila.")
        return "Maaf karen, yeh order ID nahi mila. Baraye mehrbani order ID check karen."

# Guardrail for offensive language
@guardrail
async def check_for_offensive_language(message: str):
    bad_words = ["idiot", "stupid", "dumb"]
    if any(word in message.lower() for word in bad_words):
        logger.warning(f"Offensive language mila: {message}")
        return "⚠ Baraye mehrbani baat cheet ko izzat ke sath rakhen."
    return None

# Guardrail for negative sentiment
@guardrail
async def check_for_negative_sentiment(message: str):
    negative_words = ["naraz", "nafrat", "pareshan", "bura"]
    if any(word in message.lower() for word in negative_words):
        logger.warning(f"Negative sentiment mila: {message}")
        return "Lagta hai aap naraz hain. Main aap ko human agent se jodta hoon."
    return None

# Tracking disable karo 
set_tracking_disabled(False)

# Bot agent with tools
bot_agent = Agent(
    name="BotAgent",
    instructions=(
        "You are a helpful bot that can answer FAQs and check order statuses. "
        "For FAQs, use the provided FAQ database. For order queries, use the get_order_status tool. "
        "If the query is complex or cannot be handled, escalate to HumanAgent."
    ),
    tools=[get_order_status],
    model=model,
    model_setting=ModelSettings(
        tool_choices="required",
        metadata={"agent_role": "bot", "store_id": "STORE001"}
    ),
)

# Human agent for escalation
human_agent = Agent(
    name="HumanAgent",
    instructions=(
        "You are a human representative who can handle any complex or emotional queries. "
        "Provide a professional response and assure the customer that their issue is being addressed."
    ),
    model=model,
    model_setting=ModelSettings(
        tool_choices="none",
        metadata={"agent_role": "human", "store_id": "STORE001"}
    ),
)

# Triage agent (decides which agent to handoff to)
triage_agent = Agent(
    name="TriageAgent",
    instructions=(
        "You are the triage agent. "
        "Apply guardrails first to check for offensive language or negative sentiment. "
        "If the query is about orders or FAQs, send it to BotAgent. "
        "If the query is emotional, negative, or outside BotAgent’s capabilities, send it to HumanAgent."
    ),
    model=model,
    handoffs=[bot_agent, human_agent],
    model_setting=ModelSettings(
        tool_choices="none",
        metadata={"agent_role": "triage", "store_id": "STORE001"}
    ),
)

async def handle_message(user_text: str, customer_id: str) -> str:
    """
    Main function to handle incoming messages.
    It uses triage_agent to decide whether to handoff to bot_agent or human_agent.
    """
    # Guardrails apply karo
    for guard in [check_for_offensive_language, check_for_negative_sentiment]:
        guard_result = await guard(user_text)
        if guard_result:
            logger.info(f"Guardrail triggered for customer {customer_id}: {guard_result}")
            return guard_result

    # Check FAQs directly in triage for efficiency
    for faq_key, faq_answer in FAQS.items():
        if faq_key in user_text.lower():
            logger.info(f"FAQ matched for query: {user_text}")
            return faq_answer

    # Log query
    logger.info(f"TriageAgent processing query from customer {customer_id}: {user_text}")

    # Use triage_agent to process the message
    response = await triage_agent.run(
        input=user_text,
        context={"customer_id": customer_id}
    )

    logger.info(f"Response for customer {customer_id}: {response}")
    return response

# Main function to run the bot
async def main():
    test_queries = [
        "Return policy kya hai?",
        "Order ORD123 ka status check karen?",
        "Yeh stupid service hai, mujhe nafrat hai!",
        "Mere account mein complex masla hai.",
    ]

    for query in test_queries:
        response = await handle_message(query, customer_id="CUST123")
        print(f"Query: {query}\nResponse: {response}\n")

if __name__ == "__main__":
    asyncio.run(main())