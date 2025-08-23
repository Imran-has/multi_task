import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents import Agent
from config.config import model
from schema.schema import MyDataType

# Multiple hotels ka data (instructions etc. aap apni zarurat ke mutabiq update kar sakte hain)
hotels = {
    "Hotel Sannata": "Check queries for Hotel Sannata",
    "Hotel Pearl": "Check queries for Hotel Pearl",
    "Hotel Serena": "Check queries for Hotel Serena",
}

def detect_hotel_from_query(query):
    for hotel in hotels.keys():
        if hotel.lower() in query.lower():
            return hotel
    return None

class DynamicGuardrailAgent(Agent):
    async def run(self, input, context=None):
        context = context or {}
        
        hotel_name = detect_hotel_from_query(input)
        if hotel_name:
            context["hotel_name"] = hotel_name
            is_query_about_hotel = True
            reason = f"Query is about {hotel_name}."
        else:
            # Agar query mein hotel na mile, toh context se try karo
            hotel_name = context.get("hotel_name")
            if hotel_name:
                is_query_about_hotel = True
                reason = f"Using context, query assumed about {hotel_name}."
            else:
                is_query_about_hotel = False
                reason = "Hotel not specified in query or context."
        
        # Output banayen MyDataType ke mutabiq
        output_data = MyDataType(
            hotel_name=hotel_name,
            is_query_about_hotel=is_query_about_hotel,
            reason=reason
        )
        
        # Yahan aap agent instructions ko dynamically set kar sakte hain agar zarurat ho
        self.instructions = hotels.get(hotel_name, "Please specify a valid hotel.")
        
        # Parent ka run method call karein (ye aapka model ke saath interaction karega)
        result = await super().run(input, context=context)
        
        # Agar result aapke model se koi response ho to uska bhi return kar sakte hain, warna output_data return karen
        # Example: return result or output_data depending on implementation
        return output_data

# Instantiate the agent
guardrial_agent = DynamicGuardrailAgent(
    name="Guardrail Agent for Multiple Hotels",
    instructions="",  # Dynamic set hogi
    model=model,
    output_type=MyDataType
)
