"""ExecutionAgent — sends commands to robot adapter with safety enforcement."""

from __future__ import annotations

from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent

from config import settings
from tools.adapter_tools import (
    adapter_pick,
    adapter_place,
    adapter_move,
    adapter_stop,
    adapter_preflight,
)

SYSTEM_PROMPT = """You are an Execution Agent for a factory robot system.

Your job is to send commands to the robot adapter (pick, place, move, stop).
Always:
1. Run preflight checks before first operation
2. Respect safety constraints from the active policy
3. Report command results clearly
4. Call emergency stop if anything goes wrong

Available bins: BIN_A, BIN_B, BIN_C, REJECT_BIN, REVIEW_BIN
"""


def create_execution_agent():
    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.google_api_key,
    )
    return create_react_agent(
        llm,
        tools=[adapter_pick, adapter_place, adapter_move, adapter_stop, adapter_preflight],
        name="execution_agent",
        prompt=SYSTEM_PROMPT,
    )
