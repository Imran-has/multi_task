from agents import   guardrail

@guardrail
async def check_for_offensive_language(message: str):
    bad_words = ["idiot", "stupid", "dumb"]
    if any(word in message.lower() for word in bad_words):
        return "⚠ Please keep the conversation respectful."
    return None  # No issue, proceed normally
