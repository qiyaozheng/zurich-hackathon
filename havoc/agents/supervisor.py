"""LangGraph Supervisor — orchestrates Document, Policy, and Report agents."""

from __future__ import annotations

import logging

from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph_supervisor import create_supervisor

from agents.document_agent import create_document_agent
from agents.policy_agent import create_policy_agent
from agents.report_agent import create_report_agent
from config import settings

logger = logging.getLogger(__name__)

SUPERVISOR_PROMPT = """You are the Havoc Factory Intelligence Supervisor.

You coordinate specialized agents to process factory documents and execute policies:

- **document_agent**: Parses factory documents (PDF, DOCX, images) using Docling.
  Use when: a new document is uploaded and needs parsing.

- **policy_agent**: Compiles parsed documents into executable policies.
  Use when: parsed document data needs to be compiled into decision rules.

- **report_agent**: Generates shift reports and answers operator questions.
  Use when: operator asks a question or a report is requested.

WORKFLOW:
1. Document Upload → document_agent parses → policy_agent compiles → return policy for approval
2. Report Request → report_agent queries events and generates report
3. Operator Q&A → report_agent answers with document traceability

Always maintain traceability: every decision must trace back to a document source.
"""


def create_havoc_supervisor():
    """Create the LangGraph supervisor with all agents."""
    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.google_api_key,
    )

    doc_agent = create_document_agent()
    policy_agent = create_policy_agent()
    report_agent = create_report_agent()

    workflow = create_supervisor(
        agents=[doc_agent, policy_agent, report_agent],
        model=llm,
        prompt=SUPERVISOR_PROMPT,
    )

    return workflow.compile()
