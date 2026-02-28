"""ReportAgent — generates shift reports and answers operator Q&A with traceability."""

from __future__ import annotations

import json
import logging
from datetime import datetime

from langchain_core.tools import tool

from config import settings

logger = logging.getLogger(__name__)

_event_store = None
_policy_store = None


def set_stores(event_store, policy_store):
    global _event_store, _policy_store
    _event_store = event_store
    _policy_store = policy_store


@tool
async def query_events(event_type: str = "", limit: int = 50) -> str:
    """Query factory events from the event store.

    Args:
        event_type: Filter by event type (e.g., INSPECTION, DECISION). Empty for all.
        limit: Maximum number of events to return.

    Returns:
        JSON array of matching events.
    """
    from models import EventType
    if _event_store is None:
        return json.dumps([])

    et = EventType(event_type) if event_type else None
    events = await _event_store.query(event_type=et, limit=limit)
    return json.dumps([e.model_dump(mode="json") for e in events], indent=2, default=str)


@tool
async def get_shift_stats() -> str:
    """Get statistics for the current shift.

    Returns:
        JSON object with shift statistics (inspected, passed, rejected, etc.).
    """
    if _event_store is None:
        return json.dumps({})
    stats = await _event_store.get_stats()
    return stats.model_dump_json(indent=2)


@tool
async def explain_decision(part_id: str) -> str:
    """Explain why a specific part was routed to its bin, with full document traceability.

    Args:
        part_id: The part identifier to look up.

    Returns:
        Detailed explanation with document source references.
    """
    if _event_store is None:
        return "Event store not available"

    events = await _event_store.get_by_part(part_id)
    if not events:
        return f"No events found for part {part_id}"

    return json.dumps([e.model_dump(mode="json") for e in events], indent=2, default=str)


def create_report_agent():
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langgraph.prebuilt import create_react_agent

    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.google_api_key,
    )

    system_prompt = """You are a Report Agent for a factory intelligence system.

Your job is to:
1. Generate shift reports summarizing inspection results, anomalies, and recommendations
2. Answer operator questions with full document traceability
3. Explain decisions by tracing back to the source document, page, table, and cell

When answering questions:
- Always cite the source document, page number, and section
- Reference specific rule IDs and their conditions
- Include confidence levels and any operator overrides

When generating reports:
- Include summary statistics (inspected, passed, rejected, overrides)
- List anomalies with their source references
- Provide actionable recommendations
"""

    return create_react_agent(
        llm,
        tools=[query_events, get_shift_stats, explain_decision],
        name="report_agent",
        prompt=system_prompt,
    )
