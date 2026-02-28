"""DocumentAgent — deep Docling integration for document parsing."""

from __future__ import annotations

from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent

from config import settings
from tools.docling_tools import docling_convert, docling_extract_tables, docling_get_sections

SYSTEM_PROMPT = """You are a Document Parsing Agent for a factory intelligence system.

Your job is to parse factory documents using Docling and extract structured information:
- Sorting rules and decision tables
- Safety constraints and limits
- Quality inspection criteria
- Tolerance specifications
- Operator workflow steps

Use the available Docling tools to:
1. Convert documents to structured markdown
2. Extract tables with precise structure (headers, rows, cells)
3. Get document section hierarchy

Always report what you found: number of tables, sections, and key data extracted.
Preserve traceability — note which page, section, and table each piece of data came from.
"""


def create_document_agent():
    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.google_api_key,
    )
    return create_react_agent(
        llm,
        tools=[docling_convert, docling_extract_tables, docling_get_sections],
        name="document_agent",
        prompt=SYSTEM_PROMPT,
    )
