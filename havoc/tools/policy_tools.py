"""Policy compilation, validation, diffing, and evaluation tools."""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.tools import tool

from models import (
    Decision,
    DecisionRule,
    DefectInspection,
    DocumentSource,
    ExecutablePolicy,
    PartClassification,
    PolicyConflict,
    PolicyDiff,
    PolicyValidation,
)
from tools.rule_engine import evaluate_condition

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Policy Evaluation (direct pipeline — no LLM needed)
# ---------------------------------------------------------------------------

def evaluate_policy(
    classification: PartClassification,
    defects: DefectInspection,
    policy: ExecutablePolicy,
) -> Decision:
    """Evaluate classification + defects against policy rules. Returns a Decision."""

    context: dict[str, Any] = {
        "color": classification.color,
        "color_hex": classification.color_hex,
        "size_mm": classification.size_mm,
        "size_category": classification.size_category,
        "part_type": classification.part_type,
        "shape": classification.shape,
        "confidence": classification.confidence,
        "defect_detected": defects.defect_detected,
        "surface_quality": defects.surface_quality,
        "defect_count": len(defects.defects),
    }

    sorted_rules = sorted(policy.decision_rules, key=lambda r: r.priority)

    for rule in sorted_rules:
        try:
            if evaluate_condition(rule.condition, context):
                return Decision(
                    target_bin=rule.target_bin,
                    action=rule.action,
                    rule_id=rule.id,
                    rule_condition=rule.condition,
                    source=rule.source,
                    confidence=classification.confidence,
                )
        except Exception as e:
            logger.warning("Rule %s evaluation failed: %s", rule.id, e)
            continue

    return Decision(
        target_bin=policy.default_action.target_bin,
        action=policy.default_action.action,
        rule_id="DEFAULT",
        rule_condition="no_rule_matched",
        confidence=classification.confidence,
    )


# ---------------------------------------------------------------------------
# Safety Check
# ---------------------------------------------------------------------------

def check_safety(command: str, value: float, policy: ExecutablePolicy) -> tuple[bool, str]:
    """Check if a command value violates any safety constraint."""
    for constraint in policy.safety_constraints:
        if constraint.parameter == command:
            ops = {
                "<=": lambda v, t: v <= t,
                ">=": lambda v, t: v >= t,
                "==": lambda v, t: v == t,
                "<": lambda v, t: v < t,
                ">": lambda v, t: v > t,
            }
            check = ops.get(constraint.operator, lambda v, t: True)
            if not check(value, constraint.value):
                return False, (
                    f"Safety violation: {command}={value} violates "
                    f"{constraint.parameter} {constraint.operator} {constraint.value}{constraint.unit} "
                    f"(from {constraint.source.document_name if constraint.source else 'unknown'})"
                )
    return True, "OK"


# ---------------------------------------------------------------------------
# Policy Validation
# ---------------------------------------------------------------------------

def validate_policy(policy: ExecutablePolicy) -> PolicyValidation:
    """Validate a compiled policy for completeness."""
    missing: list[str] = []
    ambiguities: list[str] = []
    severity = "OK"

    if not policy.decision_rules:
        missing.append("no_decision_rules")
        severity = "CRITICAL"

    if not policy.safety_constraints:
        missing.append("no_safety_constraints")
        if severity != "CRITICAL":
            severity = "WARNING"

    if not policy.vision_instructions:
        missing.append("no_vision_instructions")
        if severity != "CRITICAL":
            severity = "WARNING"

    if not policy.inspection_criteria:
        missing.append("no_inspection_criteria")

    bins = {r.target_bin for r in policy.decision_rules}
    rule_count = len(policy.decision_rules)
    coverage = min(rule_count / 5.0, 1.0)

    return PolicyValidation(
        is_complete=severity != "CRITICAL",
        missing_elements=missing,
        severity=severity,
        coverage_pct=round(coverage, 2),
        ambiguities=ambiguities,
        conflicts=policy.conflicts,
        recommendations=[],
    )


# ---------------------------------------------------------------------------
# Policy Diffing
# ---------------------------------------------------------------------------

def diff_policies(old: ExecutablePolicy, new: ExecutablePolicy) -> list[PolicyDiff]:
    """Compare two policies and return a list of differences."""
    diffs: list[PolicyDiff] = []

    old_rules = {r.id: r for r in old.decision_rules}
    new_rules = {r.id: r for r in new.decision_rules}

    for rule_id, new_rule in new_rules.items():
        if rule_id not in old_rules:
            diffs.append(PolicyDiff(
                diff_type="RULE_ADDED",
                rule_id=rule_id,
                new_value=new_rule.condition,
                source_new=new_rule.source,
                impact=f"New rule: {new_rule.condition} → {new_rule.target_bin}",
                affected_bins=[new_rule.target_bin],
            ))
        else:
            old_rule = old_rules[rule_id]
            if old_rule.condition != new_rule.condition:
                diffs.append(PolicyDiff(
                    diff_type="RULE_MODIFIED",
                    rule_id=rule_id,
                    old_value=old_rule.condition,
                    new_value=new_rule.condition,
                    source_old=old_rule.source,
                    source_new=new_rule.source,
                    impact=f"Condition changed: {old_rule.condition} → {new_rule.condition}",
                    affected_bins=list({old_rule.target_bin, new_rule.target_bin}),
                ))
            elif old_rule.target_bin != new_rule.target_bin:
                diffs.append(PolicyDiff(
                    diff_type="RULE_MODIFIED",
                    rule_id=rule_id,
                    old_value=old_rule.target_bin,
                    new_value=new_rule.target_bin,
                    source_old=old_rule.source,
                    source_new=new_rule.source,
                    impact=f"Target changed: {old_rule.target_bin} → {new_rule.target_bin}",
                    affected_bins=[old_rule.target_bin, new_rule.target_bin],
                ))

    for rule_id in old_rules:
        if rule_id not in new_rules:
            old_rule = old_rules[rule_id]
            diffs.append(PolicyDiff(
                diff_type="RULE_REMOVED",
                rule_id=rule_id,
                old_value=old_rule.condition,
                source_old=old_rule.source,
                impact=f"Rule removed: {old_rule.condition}",
                affected_bins=[old_rule.target_bin],
            ))

    old_safety = {c.parameter: c for c in old.safety_constraints}
    new_safety = {c.parameter: c for c in new.safety_constraints}
    for param, new_c in new_safety.items():
        if param in old_safety and old_safety[param].value != new_c.value:
            diffs.append(PolicyDiff(
                diff_type="THRESHOLD_CHANGED",
                rule_id=f"safety_{param}",
                old_value=str(old_safety[param].value),
                new_value=str(new_c.value),
                source_new=new_c.source,
                impact=f"Safety threshold {param}: {old_safety[param].value} → {new_c.value}",
            ))

    return diffs


# ---------------------------------------------------------------------------
# LangChain Tools (for agent use)
# ---------------------------------------------------------------------------

@tool
def compile_policy_tool(document_markdown: str, document_name: str) -> str:
    """Compile a parsed document into an executable policy.

    This tool takes the markdown output from Docling and returns instructions
    for the LLM to compile it into a structured policy JSON.

    Args:
        document_markdown: The markdown content from Docling parsing.
        document_name: Name of the source document.

    Returns:
        Instructions for policy compilation.
    """
    return (
        f"Analyze the following document content from '{document_name}' and compile it into "
        "an executable policy. Extract:\n"
        "1. Decision rules (sorting criteria, routing rules)\n"
        "2. Safety constraints (speed limits, force limits)\n"
        "3. Inspection criteria (what to check, thresholds)\n"
        "4. Vision prompts (what the camera should look for)\n"
        "5. Operator workflow steps\n\n"
        "Return a JSON object matching the ExecutablePolicy schema.\n\n"
        f"Document content:\n{document_markdown[:8000]}"
    )


@tool
def validate_policy_tool(policy_json: str) -> str:
    """Validate a compiled policy for completeness and conflicts.

    Args:
        policy_json: JSON string of the ExecutablePolicy.

    Returns:
        Validation results as JSON.
    """
    try:
        policy = ExecutablePolicy.model_validate_json(policy_json)
        validation = validate_policy(policy)
        return validation.model_dump_json(indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})
