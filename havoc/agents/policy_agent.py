"""PolicyAgent — compiles parsed documents into executable policies."""

from __future__ import annotations

from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent

from config import settings
from tools.policy_tools import compile_policy_tool, validate_policy_tool

SYSTEM_PROMPT = """You are a Policy Compilation Agent for a factory intelligence system.

Your job is to take parsed document content (markdown with tables, text, constraints)
and compile it into an ExecutablePolicy JSON. You must:

1. Extract DECISION RULES from sorting tables:
   - Each row becomes a rule with: id, priority, condition (as evaluable string), action, target_bin
   - Conditions use format: "color == 'red' AND size_mm > 50"
   - Supported operators: ==, !=, >, <, >=, <=, AND, OR

2. Extract SAFETY CONSTRAINTS:
   - Speed limits, force limits, operating parameters
   - Each becomes: id, parameter, operator, value, unit

3. Generate VISION INSTRUCTIONS:
   - From quality criteria, create prompts for Gemini Vision
   - "classify" prompt: what to look for (color, size, shape, defects)
   - "defect" prompt: specific defect types to detect

4. Extract INSPECTION CRITERIA:
   - What constitutes a pass/fail
   - Tolerance ranges, acceptable quality levels

5. Detect AMBIGUITIES and resolve them:
   - "small parts" → define exact size threshold
   - Missing default actions → suggest MANUAL_REVIEW

6. Detect CONFLICTS between rules:
   - Overlapping conditions
   - Contradictory actions

Return the complete ExecutablePolicy as valid JSON.

IMPORTANT: For cross-document compilation, merge rules from all documents and detect
conflicts between them (e.g., different speed limits in SOP vs Machine Spec).
"""


def create_policy_agent():
    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.google_api_key,
    )
    return create_react_agent(
        llm,
        tools=[compile_policy_tool, validate_policy_tool],
        name="policy_agent",
        prompt=SYSTEM_PROMPT,
    )
