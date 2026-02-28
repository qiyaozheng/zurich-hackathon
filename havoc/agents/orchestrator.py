"""Orchestrator — Gemini Robotics-ER 1.5 as the central brain for task execution.

Replaces the previous vision_agent + execution_agent pipeline with a single
Gemini Robotics-ER call that can see, reason, and call robot functions directly.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from PIL import Image

from config import settings
from models import (
    Decision,
    DefectInspection,
    ExecutablePolicy,
    InspectionResult,
    PartClassification,
)

logger = logging.getLogger(__name__)

ROBOTICS_MODEL = "gemini-robotics-er-1.5-preview"

# ---------------------------------------------------------------------------
# Function Declarations for Gemini Function Calling
# ---------------------------------------------------------------------------

MOVE_TO_DECLARATION = {
    "name": "move_to",
    "description": (
        "Move the robot end-effector to a 3D position in workspace coordinates. "
        "Units are millimeters. The workspace origin is at the robot base."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "x": {"type": "number", "description": "X position in mm"},
            "y": {"type": "number", "description": "Y position in mm"},
            "z": {"type": "number", "description": "Z position in mm"},
        },
        "required": ["x", "y", "z"],
    },
}

GRIP_DECLARATION = {
    "name": "grip",
    "description": "Open or close the robot gripper to pick up or release objects.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["open", "close"],
                "description": "open = release object, close = grasp object",
            },
        },
        "required": ["action"],
    },
}

FUNCTION_DECLARATIONS = [MOVE_TO_DECLARATION, GRIP_DECLARATION]


# ---------------------------------------------------------------------------
# Policy Context Builder
# ---------------------------------------------------------------------------

def build_policy_context(policy: ExecutablePolicy) -> str:
    """Convert an ExecutablePolicy into a natural-language context block."""
    lines = ["## Active Policy"]

    if policy.source_documents:
        docs = ", ".join(d.document_name for d in policy.source_documents)
        lines.append(f"Source documents: {docs}")

    if policy.decision_rules:
        lines.append("\n### Decision Rules (priority order):")
        for r in sorted(policy.decision_rules, key=lambda x: x.priority):
            src = ""
            if r.source:
                src = f" [from: {r.source.document_name} p{r.source.page}]"
            lines.append(f"  {r.id} (p{r.priority}): IF {r.condition} THEN {r.action} -> {r.target_bin}{src}")

    if policy.safety_constraints:
        lines.append("\n### Safety Constraints:")
        for s in policy.safety_constraints:
            lines.append(f"  {s.id}: {s.parameter} {s.operator} {s.value}{s.unit}")

    if policy.inspection_criteria:
        lines.append("\n### Inspection Criteria:")
        for ic in policy.inspection_criteria:
            lines.append(f"  {ic.id}: {ic.description} (type: {ic.check_type}, on_fail: {ic.action_on_fail})")

    lines.append(f"\n### Default Action: {policy.default_action.action} -> {policy.default_action.target_bin}")
    return "\n".join(lines)


SYSTEM_PROMPT = """You are HAVOC, an intelligent factory robot controller powered by Gemini Robotics-ER.

You receive a camera image from a ZED 2i mounted above the workspace (top-down view).
Your job is to analyze the scene, identify parts, assess quality, and execute the active policy
by calling robot functions (move_to, grip) to sort/place parts correctly.

WORKSPACE LAYOUT:
- Camera: top-down view covering the full workspace table
- Robot: Dobot CR S0 100 with gripper
- Available bins: BIN_A, BIN_B, BIN_C, REJECT_BIN, REVIEW_BIN

WORKFLOW:
1. Analyze the image: identify the part (type, color, size, shape, defects)
2. Apply the active policy rules to decide the action
3. If robot functions are available, call move_to and grip to execute
4. Report your analysis and decision as structured JSON

When reporting your analysis, ALWAYS include a JSON block with this structure:
```json
{
  "classification": {
    "color": "<color>", "color_hex": "#RRGGBB",
    "size_mm": <float>, "size_category": "small|medium|large",
    "part_type": "<type>", "shape": "round|square|irregular",
    "confidence": <0.0-1.0>
  },
  "defect_inspection": {
    "defect_detected": <bool>,
    "defects": [],
    "surface_quality": "perfect|acceptable|poor|reject",
    "overall_confidence": <0.0-1.0>
  },
  "decision": {
    "action": "SORT|REJECT|MANUAL_REVIEW|PASS",
    "target_bin": "<bin_id>",
    "rule_id": "<which rule matched>",
    "rule_condition": "<the condition>",
    "confidence": <0.0-1.0>
  }
}
```

{policy_context}
"""


# ---------------------------------------------------------------------------
# Orchestration Engine
# ---------------------------------------------------------------------------

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    from google import genai
    _client = genai.Client(api_key=settings.google_api_key)
    return _client


async def _execute_function_call(func_call) -> dict[str, Any]:
    """Route a Gemini function call to the robot function registry."""
    from tools.robot_functions import execute_robot_function
    return await execute_robot_function(func_call.name, dict(func_call.args))


def _extract_json_from_text(text: str) -> dict | None:
    """Try to extract a JSON object from model text output."""
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _parse_inspection_result(data: dict, part_id: str) -> InspectionResult:
    """Parse the structured JSON from the model into an InspectionResult."""
    classification = PartClassification(**(data.get("classification", {})))
    defect_data = data.get("defect_inspection", {})
    defect_inspection = DefectInspection(
        defect_detected=defect_data.get("defect_detected", False),
        surface_quality=defect_data.get("surface_quality", "perfect"),
        overall_confidence=defect_data.get("overall_confidence", 0.0),
    )
    decision_data = data.get("decision", {})
    decision = Decision(
        part_id=part_id,
        target_bin=decision_data.get("target_bin", "REVIEW_BIN"),
        action=decision_data.get("action", "MANUAL_REVIEW"),
        rule_id=decision_data.get("rule_id", ""),
        rule_condition=decision_data.get("rule_condition", ""),
        confidence=decision_data.get("confidence", classification.confidence),
    )

    return InspectionResult(
        part_id=part_id,
        classification=classification,
        defect_inspection=defect_inspection,
        decision=decision,
    )


async def orchestrate_inspection(
    image: Image.Image,
    policy: ExecutablePolicy,
    part_id: str = "",
    broadcast_fn=None,
) -> InspectionResult:
    """Run a single inspection cycle using Gemini Robotics-ER 1.5.

    1. Send image + policy context to the model
    2. Process any function calls (move_to, grip) in a loop
    3. Extract the structured inspection result from the final response
    """
    from google import genai

    client = _get_client()
    policy_context = build_policy_context(policy)
    system_prompt = SYSTEM_PROMPT.replace("{policy_context}", policy_context)

    tools = genai.types.Tool(function_declarations=FUNCTION_DECLARATIONS)
    config = genai.types.GenerateContentConfig(
        tools=[tools],
        system_instruction=system_prompt,
    )

    task_prompt = (
        "Analyze this image from the top-down ZED 2i camera. "
        "Identify the part, check for defects, apply the policy rules, "
        "and decide which bin to route it to. "
        "If you can execute robot actions, do so. "
        "Always include your structured JSON analysis in your response."
    )

    contents = [task_prompt, image]
    function_call_log: list[dict] = []
    max_turns = 10
    final_text = ""

    t0 = time.time()

    for turn in range(max_turns):
        try:
            response = client.models.generate_content(
                model=settings.gemini_orchestrator_model,
                contents=contents,
                config=config,
            )
        except Exception as e:
            logger.error("Robotics-ER call failed (turn %d): %s", turn, e)
            break

        if not response.candidates:
            logger.warning("No candidates in response (turn %d)", turn)
            break

        candidate = response.candidates[0]
        has_function_call = False

        for part in candidate.content.parts:
            if hasattr(part, "function_call") and part.function_call:
                has_function_call = True
                fc = part.function_call
                logger.info("Function call: %s(%s)", fc.name, dict(fc.args))

                result = await _execute_function_call(fc)
                function_call_log.append({
                    "function": fc.name,
                    "args": dict(fc.args),
                    "result": result,
                })

                if broadcast_fn:
                    try:
                        await broadcast_fn({
                            "type": "command",
                            "data": {"function": fc.name, "args": dict(fc.args), "result": result},
                        })
                    except Exception:
                        pass

                contents = [
                    candidate.content,
                    genai.types.Content(
                        role="function",
                        parts=[genai.types.Part(
                            function_response=genai.types.FunctionResponse(
                                name=fc.name,
                                response=result,
                            )
                        )],
                    ),
                ]

            if hasattr(part, "text") and part.text:
                final_text = part.text

        if not has_function_call:
            break

    elapsed_ms = (time.time() - t0) * 1000
    logger.info("Orchestration completed in %.0fms (%d function calls)", elapsed_ms, len(function_call_log))

    parsed = _extract_json_from_text(final_text)
    if parsed:
        result = _parse_inspection_result(parsed, part_id)
    else:
        logger.warning("Could not extract structured JSON from model response, using defaults")
        result = InspectionResult(
            part_id=part_id,
            classification=PartClassification(confidence=0.0),
            defect_inspection=DefectInspection(),
            decision=Decision(
                part_id=part_id,
                action="MANUAL_REVIEW",
                target_bin="REVIEW_BIN",
                rule_id="FALLBACK",
            ),
        )

    return result


async def orchestrate_free_task(
    task: str,
    image: Image.Image | None = None,
    policy: ExecutablePolicy | None = None,
    broadcast_fn=None,
) -> dict[str, Any]:
    """Execute a free-form task using Gemini Robotics-ER 1.5.

    Unlike orchestrate_inspection, this handles arbitrary operator commands
    like "sort all parts on the table" or "move the red part to BIN_A".
    """
    from google import genai

    client = _get_client()

    policy_context = build_policy_context(policy) if policy else "No active policy."
    system_prompt = SYSTEM_PROMPT.replace("{policy_context}", policy_context)

    tools = genai.types.Tool(function_declarations=FUNCTION_DECLARATIONS)
    config = genai.types.GenerateContentConfig(
        tools=[tools],
        system_instruction=system_prompt,
    )

    contents: list = [task]
    if image:
        contents.append(image)

    steps: list[dict] = []
    max_turns = 20
    final_text = ""

    for turn in range(max_turns):
        try:
            response = client.models.generate_content(
                model=settings.gemini_orchestrator_model,
                contents=contents,
                config=config,
            )
        except Exception as e:
            logger.error("Free task call failed (turn %d): %s", turn, e)
            steps.append({"error": str(e), "turn": turn})
            break

        if not response.candidates:
            break

        candidate = response.candidates[0]
        has_function_call = False

        for part in candidate.content.parts:
            if hasattr(part, "function_call") and part.function_call:
                has_function_call = True
                fc = part.function_call
                logger.info("Free task function call: %s(%s)", fc.name, dict(fc.args))

                result = await _execute_function_call(fc)
                steps.append({
                    "turn": turn,
                    "function": fc.name,
                    "args": dict(fc.args),
                    "result": result,
                })

                if broadcast_fn:
                    try:
                        await broadcast_fn({
                            "type": "command",
                            "data": {"function": fc.name, "args": dict(fc.args), "result": result},
                        })
                    except Exception:
                        pass

                contents = [
                    candidate.content,
                    genai.types.Content(
                        role="function",
                        parts=[genai.types.Part(
                            function_response=genai.types.FunctionResponse(
                                name=fc.name,
                                response=result,
                            )
                        )],
                    ),
                ]

            if hasattr(part, "text") and part.text:
                final_text = part.text

        if not has_function_call:
            break

    return {
        "task": task,
        "steps": steps,
        "total_function_calls": len(steps),
        "summary": final_text,
    }
