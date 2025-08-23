

import asyncio
from typing import Optional, Dict, Any

# === Assume these come from your OpenAI Agent SDK ===
# Aapke project me ye paths different ho sakte hain (e.g., from agents import Agent, Runner, function_tool, guardrail, ItemHelpers)
try:
    from agents import Agent, Runner, function_tool, guardrail, ItemHelpers
    from config.config import model
except Exception:
    # Fallback mock (sirf editor warnings se bachne ke liye). Actual run ke liye asli SDK required hoga.
    class Agent:  # type: ignore
        def __init__(self, name: str, instructions: str, model: Optional[str] = None, tools: Optional[list] = None):
            self.name = name
            self.instructions = instructions
            self.model = model
            self.tools = tools or []

    class Runner:  # type: ignore
        def __init__(self, agent: Agent):
            self.agent = agent

        async def run_streamed(self, input: str, *, metadata: Optional[Dict[str, Any]] = None, model_settings: Optional[Dict[str, Any]] = None):
            # Dummy async generator for demonstration
            class _Dummy:
                async def stream_events(self):
                    # In real SDK, yahan events aate hain (tool calls, messages, handoffs, etc.)
                    yield type("Evt", (), {"item": type("It", (), {"type": "message", "content": f"(MOCK) {input}"})})
            return _Dummy()

    def function_tool(*dargs, **dkwargs):  # type: ignore
        def deco(fn):
            fn._is_function_tool = True
            fn._tool_kwargs = dkwargs
            return fn
        return deco

    def guardrail(fn):  # type: ignore
        fn._is_guardrail = True
        return fn

    class ItemHelpers:  # type: ignore
        @staticmethod
        def text_message_output(item):
            return getattr(item, "content", "")

# === Simple in-memory order DB (simulate API) ===
FAKE_ORDERS: Dict[str, Dict[str, str]] = {
    "123": {"status": "Shipped", "eta": "2-3 days", "carrier": "FastEx"},
    "456": {"status": "Processing", "eta": "5-7 days", "carrier": "LogiPak"},
    "789": {"status": "Delivered", "eta": "—", "carrier": "FastEx"},
}

# === Logging Helper ===
def log_event(event_type: str, details: Dict[str, Any]):
    print(f"[LOG] {event_type}: {details}")

# === Guardrail: Offensive / Negative language detection ===
@guardrail
def language_guardrail(user_text: str) -> bool:
    """True = allowed, False = blocked"""
    bad_words = ["idiot", "stupid", "bkwas", "lanat", "gali", "bewaqoof"]
    text = (user_text or "").lower()
    if any(w in text for w in bad_words):
        return False
    return True

# === Utility: basic sentiment check ===
def is_negative_sentiment(user_text: str) -> bool:
    neg_markers = ["refund now", "very bad", "worst", "angry", "nonsense", "bkwas", "ghalat", "cancel karo"]
    t = (user_text or "").lower()
    return any(m in t for m in neg_markers)

# === Function Tool: get_order_status with is_enabled + error_function ===

def _is_order_query(user_text: str) -> bool:
    t = (user_text or "").lower()
    return any(k in t for k in ["order", "status", "tracking", "track", "order id", "meray order ka", "mera order", "id "])


def _friendly_order_not_found(order_id: str) -> str:
    return (
        f"😕 Roman Urdu: Lagta hai order_id '{order_id}' hamari system me nahi mila.\n"
        "Meherbani karke sahi order ID share karein (jaise 123, 456, 789). Agar phir bhi masla ho to main Human Agent ko forward kardunga."
    )


@function_tool(
    name="get_order_status",
    description="Simulated order status checker",
    is_enabled=lambda query: _is_order_query(query.get("user_text", "")),
    error_function=lambda *args, **kwargs: _friendly_order_not_found(kwargs.get("order_id", "(missing)")),
)
def get_order_status(order_id: str) -> str:
    # Roman Urdu: Yahan normally API/database call hoti. Hum fake dict use kar rahe hain.
    log_event("tool_invocation", {"tool": "get_order_status", "order_id": order_id})
    data = FAKE_ORDERS.get(order_id)
    if not data:
        # Real SDK error_function ko trigger karne ke liye exception
        raise ValueError("ORDER_NOT_FOUND")
    return (
        f"Order {order_id}: Status = {data['status']}, ETA = {data['eta']}, Carrier = {data['carrier']}"
    )

# === FAQs (simple hard-coded) ===
FAQS: Dict[str, str] = {
    "return policy": "Hamari return policy 30 din ki hai. Item unused ho aur receipt ho to asani se return ho jata hai.",
    "shipping time": "Standard shipping 3-5 din me deliver hoti hai. Express 1-2 din.",
    "payment methods": "Hum COD, Credit/Debit cards aur bank transfer accept karte hain.",
}


def try_faq_answer(user_text: str) -> Optional[str]:
    text = (user_text or "").lower()
    if "return" in text:
        return FAQS["return policy"]
    if "shipping" in text or "delivery" in text:
        return FAQS["shipping time"]
    if "payment" in text or "card" in text or "cod" in text:
        return FAQS["payment methods"]
    return None


# === Agents ===
BOT_INSTRUCTIONS = (
    "Aap ek friendly Customer Support Bot hain. Roman Urdu me madad dein.\n"
    "1) Pehle guardrails chalaen.\n"
    "2) Agar order se related query ho to get_order_status tool use karen.\n"
    "3) Simple FAQs ka direct jawab dein.\n"
    "4) Agar complex/negative ho to Human Agent ko handoff karen.\n"

)

HUMAN_INSTRUCTIONS = (
    "Aap Human Support Agent hain. Roman Urdu me professional tone me masail hal karen."
)


bot_agent = Agent(
    name="BotAgent",
    instructions=BOT_INSTRUCTIONS,
    model="gpt-5-mini",  # aap apna model yahan set kar sakte hain
    tools=[get_order_status],
    gemini_model=model
)

human_agent = Agent(
    name="HumanAgent",
    instructions=HUMAN_INSTRUCTIONS,
    gemini_model=model,

)


bot_agent = Agent(
    name="BotAgent",
    instructions=BOT_INSTRUCTIONS,
    model="gpt-5-mini",  # aap apna model yahan set kar sakte hain
    tools=[get_order_status],
    gemini_model=model
)

# === Orchestrator ===
async def handle_message(user_text: str, customer_id: str) -> None:
    # 1) Guardrail
    if not language_guardrail(user_text):
        print(
            "⚠️ Barah-e-karam guftagu me respect barqarar rakhein. Meherbani karke apna message rephrase karein."
        )
        log_event("guardrail_block", {"text": user_text})
        return

    # 2) Handoff check (negative sentiment or complex)
    # Pehle check karte hain ke FAQs ya orders ke ilawa kuch bohat complex to nahi
    faq = try_faq_answer(user_text)
    order_like = _is_order_query(user_text)

    if is_negative_sentiment(user_text):
        # Negative tone -> HumanAgent
        log_event("handoff", {"reason": "negative_sentiment", "to": "HumanAgent"})
        await run_with_agent(human_agent, user_text, customer_id, tool_choice="auto")
        return

    # 3) Agar FAQ match ho to direct jawab
    if faq and not order_like:
        print(f"🤖 (Bot) FAQ: {faq}")
        log_event("faq_answered", {"faq": faq})
        return

    # 4) Agar order query lag rahi ho, tool try karo
    if order_like:
        # Yahan hum tool ko LLM ke through bhi chalwa sakte hain (tool_choice="auto").
        # For clarity, hum direct tool ko call kar rahe hain (SDK ke mutabiq aap LLM-run me bhi chalwa sakte hain).
        order_id = extract_order_id(user_text)
        if not order_id:
            print("🤖 (Bot) Meherbani karke apni order ID share karein (e.g., 123, 456, 789).")
            return
        try:
            result = get_order_status(order_id=order_id)  # SDK: tool will validate via is_enabled
            print(f"📦 (Bot) {result}")
            return
        except Exception:
            # error_function ka friendly output
            print(_friendly_order_not_found(order_id))
            return

    # 5) Agar na FAQ na order, to try bot via LLM; agar still ambiguous -> handoff
    model_settings = {
        "tool_choice": "auto",  # "required" bhi try karke dikha sakte hain
        "metadata": {"customer_id": customer_id, "channel": "chat"},
    }

    # Bot se try karein
    ok = await run_with_agent(bot_agent, user_text, customer_id, **model_settings)

    if not ok:
        # Agar bot confident nahi, to human ko de dein
        log_event("handoff", {"reason": "no_clear_answer", "to": "HumanAgent"})
        await run_with_agent(human_agent, user_text, customer_id, tool_choice="auto")


async def run_with_agent(agent: Agent, user_text: str, customer_id: str, **model_settings):
    print(f"\n--- {agent.name} ko message diya gaya ---")
    print(f"👤 (User-{customer_id}): {user_text}")

    runner = Runner(agent)
    try:
        result = await runner.run_streamed(
            input=user_text,
            metadata={"customer_id": customer_id},
            model_settings=model_settings or {"tool_choice": "auto"},
        )

        confident = False
        async for event in result.stream_events():
            # Roman Urdu: SDK ke events me alag types ho sakte hain (message, tool_call, tool_result, handoff, error, etc.)
            item = event.item
            itype = getattr(item, "type", "message")

            if itype == "message":
                print(f"💬 ({agent.name}): {ItemHelpers.text_message_output(item)}")
                confident = True

            elif itype == "tool_call_item":
                log_event("tool_call", {"agent": agent.name, "tool": getattr(item, "name", "unknown")})
            elif itype == "tool_result_item":
                log_event("tool_result", {"agent": agent.name, "result": getattr(item, "output", "")})
            elif itype == "handoff_item":
                log_event("handoff_event", {"from": agent.name, "to": "HumanAgent"})
                confident = False
            elif itype == "error":
                log_event("agent_error", {"agent": agent.name})
                confident = False

        return confident

    except Exception as e:
        log_event("runner_exception", {"agent": agent.name, "error": str(e)})
        return False


# === Helpers ===
def extract_order_id(text: str) -> Optional[str]:
    # Roman Urdu: Aasan tareeqa — pehle number token dhoondo
    if not text:
        return None
    tokens = text.replace("#", " ").replace(":", " ").split()
    for tok in tokens:
        if tok.isdigit():
            return tok
    # Kuch patterns: ID123, O-456, etc.
    for tok in tokens:
        num = "".join(ch for ch in tok if ch.isdigit())
        if num:
            return num
    return None


# === Demo main ===
async def main():
    print("\n===== Smart Customer Support Bot (Roman Urdu) Demo =====\n")

    # 1) Friendly FAQ
    await handle_message("Return policy kya hai?", customer_id="CUST-1001")

    # 2) Order status (valid)
    await handle_message("Mera order status check karo, order id 123 hai.", customer_id="CUST-1002")

    # 3) Order status (invalid)
    await handle_message("Order ID 999 ka status?", customer_id="CUST-1003")

    # 4) Negative sentiment -> Human handoff
    await handle_message("Your service is worst, refund now!", customer_id="CUST-1004")

    # 5) Unknown but polite -> Bot tries, then may handoff
    await handle_message("Kya aap gift wrapping provide karte hain?", customer_id="CUST-1005")

    # 6) Offensive language -> Guardrail block
    await handle_message("Tum log bkwas ho", customer_id="CUST-1006")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError:
        # Some environments (e.g., nested loops) need this fallback
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
