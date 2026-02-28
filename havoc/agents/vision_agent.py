"""VisionAgent — multi-mode Gemini Vision inspection (direct pipeline, no supervisor)."""

from __future__ import annotations

import logging

from PIL import Image

from models import (
    Decision,
    DefectInspection,
    ExecutablePolicy,
    InspectionResult,
    PartClassification,
)
from tools.policy_tools import evaluate_policy
from tools.vision_tools import gemini_classify, gemini_inspect_defects

logger = logging.getLogger(__name__)

DEFAULT_CLASSIFY_PROMPT = (
    "Analyze this factory part. Determine: "
    "1) dominant color (red/blue/green/yellow/other), "
    "2) estimated size in millimeters, "
    "3) shape (round/square/irregular), "
    "4) any visible defects. "
    "Be precise with the size estimate."
)

DEFAULT_DEFECT_PROMPT = (
    "Inspect this factory part for quality defects. Look for: "
    "cracks, scratches, discoloration, dents, chips, contamination. "
    "Rate the surface quality and severity of any defects found."
)


async def run_inspection(
    image: Image.Image,
    policy: ExecutablePolicy,
    part_id: str = "",
) -> InspectionResult:
    """Full inspection pipeline: classify → defect check → policy decision.

    This runs as a direct async pipeline — no LangGraph supervisor overhead.
    """
    classify_prompt = DEFAULT_CLASSIFY_PROMPT
    defect_prompt = DEFAULT_DEFECT_PROMPT

    if "classify" in policy.vision_instructions:
        classify_prompt = policy.vision_instructions["classify"].prompt
    if "defect" in policy.vision_instructions:
        defect_prompt = policy.vision_instructions["defect"].prompt

    classification = await gemini_classify(image, classify_prompt)
    logger.info(
        "Classification: %s %smm (conf: %.2f)",
        classification.color, classification.size_mm, classification.confidence,
    )

    defects = DefectInspection()
    if classification.confidence >= 0.3:
        defects = await gemini_inspect_defects(image, defect_prompt)
        logger.info(
            "Defects: detected=%s quality=%s (conf: %.2f)",
            defects.defect_detected, defects.surface_quality, defects.overall_confidence,
        )

    decision = evaluate_policy(classification, defects, policy)
    if part_id:
        decision.part_id = part_id

    logger.info(
        "Decision: %s → %s (rule: %s)",
        decision.part_id, decision.target_bin, decision.rule_id,
    )

    return InspectionResult(
        part_id=decision.part_id,
        classification=classification,
        defect_inspection=defects,
        decision=decision,
    )
