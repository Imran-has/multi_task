


from typing import Dict, Optional, Any, List, Tuple
from pydantic import BaseModel
import re
from guardrail.input_guardrail import guardrial_input_function

from agents import Agent, function_tool, Runner, RunContextWrapper
from config.config import MODEL


# ----------------------------
# In-memory multi-hotel storage
# ----------------------------
# You can replace this with a DB later; keep the same interface.
HOTEL_DB: Dict[str, Dict[str, Any]] = {
    "hotel sannata": {
        "name": "Hotel Sannata",
        "owner": "Mr. Ratan Lal",
        "total_rooms": 200,
        "blocked_rooms": 20,  # not available for public (special guests)
        "amenities": ["Free Wi-Fi", "Breakfast", "Gym", "Pool"],
        "address": "Main Bazar, Karachi",
        "phone": "+92-300-1234567",
        "notes": "20 rooms reserved for special guests.",
    },
    "hotel blue bay": {
        "name": "Hotel Blue Bay",
        "owner": "Ayesha Khan",
        "total_rooms": 120,
        "blocked_rooms": 10,
        "amenities": ["Sea View", "Wi-Fi", "Restaurant"],
        "address": "Clifton, Karachi",
        "phone": "+92-311-1111111",
        "notes": "Popular for sea-facing rooms.",
    },
    "hotel grand palace": {
        "name": "Hotel Grand Palace",
        "owner": "Mr. Ahmed Ali",
        "total_rooms": 300,
        "blocked_rooms": 25,
        "amenities": ["Wi-Fi", "Conference Hall", "Swimming Pool", "Spa"],
        "address": "Mall Road, Lahore",
        "phone": "+92-321-2222222",
        "notes": "Luxury hotel in the heart of the city.",
    }
}

# ----------------------------
# Utility helpers
# ----------------------------

def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _find_hotel_candidates(message: str) -> List[Tuple[str, float]]:
    """Very light-weight candidate finder.
    Returns (key, score). Score is simple token overlap; replace with better NER if needed.
    """
    msg = _normalize(message)
    candidates: List[Tuple[str, float]] = []
    msg_tokens = set(re.findall(r"[a-z0-9']+", msg))
    for key, data in HOTEL_DB.items():
        name_tokens = set(re.findall(r"[a-z0-9']+", _normalize(data.get("name", key))))
        overlap = len(msg_tokens & name_tokens)
        score = overlap / max(1, len(name_tokens))
        if overlap > 0:
            candidates.append((key, score))
    # Sort by score desc
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates


def _pick_active_hotel(context: RunContextWrapper) -> Optional[str]:
    """Decide which hotel is active based on:
    1) Previously set context.state["active_hotel"].
    2) Latest user message text.
    """
    # 1) Persisted in state?
    active = context.state.get("active_hotel")
    if active:
        return active if active in HOTEL_DB else None

    # 2) Infer from the latest user message
    last_user = context.latest_user_message or ""
    if last_user:
        cands = _find_hotel_candidates(last_user)
        if cands:
            key = cands[0][0]
            context.state["active_hotel"] = key
            return key

    return None


# ----------------------------
# Tools (function_tool) — allow updating/reading hotel data
# ----------------------------

class HotelRecord(BaseModel):
    name: str
    owner: Optional[str] = None
    total_rooms: Optional[int] = None
    blocked_rooms: Optional[int] = None
    amenities: Optional[List[str]] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None


@function_tool
def add_or_update_hotel(payload: HotelRecord) -> str:
    """Create or update a hotel's profile. Returns a confirmation string.
   
    {
      "name": "Hotel Blue Bay",
      "owner": "Ayesha Khan",
      "total_rooms": 120,
      "blocked_rooms": 10,
      "amenities": ["Wi‑Fi", "Breakfast"],
      "address": "Clifton, Karachi",
      "phone": "+92-311-1111111",
      "notes": "Sea view."
    }
    """
    key = _normalize(payload.name)
    existing = HOTEL_DB.get(key, {})
    updated = {**existing}

    for field, value in payload.model_dump(exclude_none=True).items():
        updated[field] = value

    # Ensure canonical name always saved
    updated["name"] = payload.name

    HOTEL_DB[key] = updated
    return f"Saved hotel: {updated['name']} (key: {key})."


@function_tool
def list_hotels() -> List[str]:
    """List all hotel names currently registered."""
    return [data.get("name", key) for key, data in HOTEL_DB.items()]


@function_tool
def get_hotel_info(name: Optional[str] = None, use_active_if_missing: bool = True, context: Optional[RunContextWrapper] = None) -> Dict[str, Any]:
    """Get a hotel's info by name. If name is missing and use_active_if_missing=True, use active hotel from context."""
    key: Optional[str] = _normalize(name) if name else None

    if not key and use_active_if_missing and context is not None:
        key = _pick_active_hotel(context)

    if not key:
        return {"error": "No hotel specified. Please provide a hotel name."}

    rec = HOTEL_DB.get(key)
    if not rec:
        return {"error": f"Hotel not found: {name or key}"}

    # Also set it as active in context (session continuity)
    if context is not None:
        context.state["active_hotel"] = key

    # Compute public availability
    total = rec.get("total_rooms")
    blocked = rec.get("blocked_rooms") or 0
    public_capacity = total - blocked if isinstance(total, int) else None

    return {
        **rec,
        "public_capacity": public_capacity,
    }


# ----------------------------
# Optional: Simple output schema for classification (kept from user's snippet idea)
# ----------------------------
class HotelQueryClassification(BaseModel):
    is_query_about_active_hotel: bool
    reason: str


# ----------------------------
# Dynamic instructions
# ----------------------------

def dynamic_instructions(context: RunContextWrapper, agent: Agent) -> str:
    """Return instructions specialized to the active (or inferred) hotel.
    This replaces the old static instructions.
    """
    active_key = _pick_active_hotel(context)

    base_rules = (
        "You are a helpful hotel customer care assistant.\n"
        "- Always be concise, correct, and friendly.\n"
        "- If the user asks about bookings, availability, pricing, or amenities, answer for the active hotel.\n"
        "- If you are not sure which hotel is meant, ask the user to specify the hotel name, and show a short list of known hotels.\n"
        "- If the user switches hotel mid-conversation (mentions another hotel), update the active hotel accordingly.\n"
    )

    if not active_key:
        # No hotel inferred yet — provide neutral instructions, plus guidance to ask for hotel.
        hotels = ", ".join(sorted([h.get("name", k) for k, h in HOTEL_DB.items()])) or "(no hotels registered)"
        return (
            base_rules
            + f"\nCurrently no active hotel is selected. Known hotels: {hotels}. Ask the user which hotel they mean.\n"
        )

    rec = HOTEL_DB.get(active_key, {})
    name = rec.get("name", active_key.title())
    owner = rec.get("owner", "(owner unknown)")
    total = rec.get("total_rooms", "(unknown)")
    blocked = rec.get("blocked_rooms", 0)
    public_capacity = total - blocked if isinstance(total, int) else "(unknown)"
    amenities = rec.get("amenities") or []
    address = rec.get("address", "(address unknown)")
    phone = rec.get("phone", "(phone unknown)")
    notes = rec.get("notes", "")

    hotel_profile = (
        f"Active Hotel Profile:\n"
        f"- Hotel name: {name}\n"
        f"- Owner: {owner}\n"
        f"- Total rooms: {total}\n"
        f"- Rooms blocked (special guests): {blocked}\n"
        f"- Public capacity (bookable): {public_capacity}\n"
        f"- Amenities: {', '.join(amenities) if amenities else '(none specified)'}\n"
        f"- Address: {address}\n"
        f"- Phone: {phone}\n"
        f"- Notes: {notes}\n"
    )

    behavior = (
        "Answer **only** for the active hotel unless the user clearly asks you to compare hotels.\n"
        "When asked for availability, compute using public capacity if relevant.\n"
        "If user provides new facts (e.g., updated room counts), use tools to update the hotel record.\n"
    )

    return base_rules + "\n" + hotel_profile + "\n" + behavior


# ----------------------------
# Agent definition
# ----------------------------

hotel_assistant = Agent(
    name="Hotel Customer Care",
    model=MODEL,
    instructions=dynamic_instructions,  # <— dynamic
    tools=[add_or_update_hotel, list_hotels, get_hotel_info],
    input_guardrails=[guardrial_input_function],
    output_guardrails=[],
    output_schema=HotelQueryClassification,  # Optional: model can fill this, useful for logging/analytics
)


# ----------------------------
# Small demo (optional) — run via: `python -m bilal_fareed_code.my_agent.hotel_assistant`
# ----------------------------
if __name__ == "__main__":
    # Simple interactive runner for local testing
    runner = Runner(hotel_assistant)

    print("Type your messages. Try: 'Tell me about Hotel Sannata availability' or 'Add Hotel Blue Bay'\n")
    try:
        while True:
            msg = input("You: ")
            if not msg:
                continue
            if msg.lower() in {"exit", "quit"}:
                break

            # Lightweight command to show how to add quickly without JSON tool call
            if msg.lower().startswith("add hotel "):
                name = msg[10:].strip()
                add_or_update_hotel(HotelRecord(name=name))
                print(f"[Local] Added with defaults: {name}")
                continue

            # Normal LLM turn
            resp = runner.run(msg)
            print(f"Assistant: {resp.output_text}")

    except KeyboardInterrupt:
        pass
