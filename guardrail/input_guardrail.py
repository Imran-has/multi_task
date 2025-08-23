import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from typing import Any

from agents import (
    Agent,
    GuardrailFunctionOutput,
    InputGuardrailTripwireTriggered,
    OutputGuardrailTripwireTriggered,
    RunContextWrapper,
    Runner,
    
    TResponseInputItem,
    input_guardrail,
    output_guardrail,
    set_tracing_disabled,
)

import asyncio
from pydantic import BaseModel

from config.config import model


# ===================== INPUT GUARDRAIL =====================
class MathOutPut(BaseModel):
    is_math: bool
    reason: str
set_tracing_disabled(True)  # Disable tracing for guardrails

@input_guardrail
async def check_input(
    ctx: RunContextWrapper[Any], agent: Agent[Any], input_data: str | list[TResponseInputItem]
) -> GuardrailFunctionOutput:
    input_agent = Agent(
        "InputGuardrailAgent",
        instructions="Check if the user input is related to mathematics only.",
        model=model,
        output_type=MathOutPut,
          # Ensure the model is set for the input agent
    )
    result = await Runner.run(input_agent, input_data, context=ctx.context)
    final_output = result.final_output

    return GuardrailFunctionOutput(
        output_info=final_output, tripwire_triggered=not final_output.is_math
    )


# ===================== OUTPUT GUARDRAIL =====================
class PoliticalOutput(BaseModel):
    is_political: bool
    reason: str

@output_guardrail
async def check_output(
    ctx: RunContextWrapper[Any], agent: Agent[Any], output_data: str
) -> GuardrailFunctionOutput:
    output_agent = Agent(
        "OutputGuardrailAgent",
        instructions=(
            "Check if the output contains any political topics, "
            "political opinions, or references to political figures."
        ),
        model=model,
        output_type=PoliticalOutput,
    )
    result = await Runner.run(output_agent, output_data, context=ctx.context)
    final_output = result.final_output

    return GuardrailFunctionOutput(
        output_info=final_output, tripwire_triggered=final_output.is_political
    )


# ===================== AGENTS =====================
math_agent = Agent(
    "MathAgent",
    instructions="You are a math agent. Answer only math-related questions.",
    model=model,
    input_guardrails=[check_input],
    output_guardrails=[check_output]  # Added here

)

general_agent = Agent(
    "GeneralAgent",
    instructions="You are a helpful general-purpose agent.",
    model=model,
    output_guardrails=[check_output]  # Added here too
    
)


# ===================== MAIN FUNCTION =====================
async def main():
    try:
        msg = input("Enter your question: ")
        result = await Runner.run(math_agent, msg)
        print(f"\nFinal Output: {result.final_output}")

    except InputGuardrailTripwireTriggered:
        print("Error: Invalid prompt (Not math related).")
    except OutputGuardrailTripwireTriggered:
        print("Error: Output contains political content.")


asyncio.run(main())
