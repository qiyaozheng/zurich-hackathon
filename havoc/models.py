from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Document Source & Traceability
# ---------------------------------------------------------------------------

class DocumentSource(BaseModel):
    document_id: str
    document_name: str
    page: int = 0
    section: str = ""
    table_id: str | None = None
    row: int | None = None
    cell_text: str = ""
    bbox: list[float] | None = None
    confidence: float = 1.0


class ParsedDocument(BaseModel):
    document_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    format: str
    pages: int = 0
    tables_found: int = 0
    sections: list[str] = Field(default_factory=list)
    markdown: str = ""
    raw_dict: dict[str, Any] = Field(default_factory=dict)
    tables_data: list[dict[str, Any]] = Field(default_factory=list)
    parse_time_ms: float = 0


# ---------------------------------------------------------------------------
# Vision Models
# ---------------------------------------------------------------------------

class PartClassification(BaseModel):
    color: str = "unknown"
    color_hex: str = "#000000"
    size_mm: float = 0.0
    size_category: Literal["small", "medium", "large"] = "medium"
    part_type: str = "unknown"
    shape: Literal["round", "square", "irregular"] = "irregular"
    confidence: float = 0.0


class DefectDetail(BaseModel):
    type: Literal["crack", "scratch", "discoloration", "dent", "chip", "contamination"] = "scratch"
    severity: Literal["minor", "major", "critical"] = "minor"
    location: str = "center"
    confidence: float = 0.0


class DefectInspection(BaseModel):
    defect_detected: bool = False
    defects: list[DefectDetail] = Field(default_factory=list)
    surface_quality: Literal["perfect", "acceptable", "poor", "reject"] = "perfect"
    overall_confidence: float = 0.0



# ---------------------------------------------------------------------------
# Policy Models
# ---------------------------------------------------------------------------

class VisionPrompt(BaseModel):
    prompt: str
    model: str = "gemini-2.5-pro"
    mode: Literal["classify", "defect", "verify"] = "classify"


class DecisionRule(BaseModel):
    id: str
    priority: int = 0
    condition: str
    action: Literal["SORT", "REJECT", "MANUAL_REVIEW", "PASS"] = "SORT"
    target_bin: str = ""
    source: DocumentSource | None = None


class SafetyConstraint(BaseModel):
    id: str
    parameter: str
    operator: Literal["<=", ">=", "==", "<", ">"] = "<="
    value: float
    unit: str = ""
    source: DocumentSource | None = None


class InspectionCriterion(BaseModel):
    id: str
    description: str
    check_type: Literal["visual", "dimensional", "surface"] = "visual"
    threshold: float | None = None
    action_on_fail: Literal["REJECT", "MANUAL_REVIEW", "FLAG"] = "REJECT"
    source: DocumentSource | None = None


class WorkflowStep(BaseModel):
    step: int
    instruction: str
    requires_confirmation: bool = False
    source: DocumentSource | None = None


class DefaultAction(BaseModel):
    action: Literal["MANUAL_REVIEW", "REJECT", "PASS"] = "MANUAL_REVIEW"
    target_bin: str = "REVIEW_BIN"


class PolicyConflict(BaseModel):
    conflict_type: Literal["VALUE_MISMATCH", "RULE_OVERLAP", "MISSING_IN_ONE"] = "VALUE_MISMATCH"
    description: str = ""
    doc_a: DocumentSource | None = None
    doc_b: DocumentSource | None = None
    resolution: str = ""
    requires_human: bool = True


class PolicyValidation(BaseModel):
    is_complete: bool = False
    missing_elements: list[str] = Field(default_factory=list)
    severity: Literal["OK", "WARNING", "CRITICAL"] = "OK"
    coverage_pct: float = 0.0
    ambiguities: list[str] = Field(default_factory=list)
    conflicts: list[PolicyConflict] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class PolicyStatus(str, Enum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    SUSPENDED = "SUSPENDED"
    REJECTED = "REJECTED"


class ExecutablePolicy(BaseModel):
    policy_id: str = Field(default_factory=lambda: f"policy-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}")
    source_documents: list[DocumentSource] = Field(default_factory=list)
    version: int = 1
    status: PolicyStatus = PolicyStatus.DRAFT
    created_at: datetime = Field(default_factory=datetime.utcnow)

    decision_rules: list[DecisionRule] = Field(default_factory=list)
    safety_constraints: list[SafetyConstraint] = Field(default_factory=list)
    inspection_criteria: list[InspectionCriterion] = Field(default_factory=list)
    vision_instructions: dict[str, VisionPrompt] = Field(default_factory=dict)
    operator_workflows: list[WorkflowStep] = Field(default_factory=list)

    default_action: DefaultAction = Field(default_factory=DefaultAction)
    conflicts: list[PolicyConflict] = Field(default_factory=list)
    validation: PolicyValidation = Field(default_factory=PolicyValidation)

    execution_sequence: list[str] = Field(
        default_factory=lambda: ["VISION_CLASSIFY", "VISION_DEFECT", "POLICY_DECIDE", "ROUTE_TO_BIN"]
    )



# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------

class Decision(BaseModel):
    part_id: str = Field(default_factory=lambda: f"part-{uuid.uuid4().hex[:8]}")
    target_bin: str = "REVIEW_BIN"
    action: Literal["SORT", "REJECT", "MANUAL_REVIEW", "PASS"] = "SORT"
    rule_id: str = ""
    rule_condition: str = ""
    source: DocumentSource | None = None
    confidence: float = 0.0
    requires_operator: bool = False


# ---------------------------------------------------------------------------
# Inspection Result (combined)
# ---------------------------------------------------------------------------

class InspectionResult(BaseModel):
    part_id: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    classification: PartClassification = Field(default_factory=PartClassification)
    defect_inspection: DefectInspection = Field(default_factory=DefectInspection)
    decision: Decision = Field(default_factory=Decision)
    image_base64: str | None = None


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

class EventType(str, Enum):
    DOCUMENT_PARSED = "DOCUMENT_PARSED"
    POLICY_COMPILED = "POLICY_COMPILED"
    POLICY_APPROVED = "POLICY_APPROVED"
    POLICY_REJECTED = "POLICY_REJECTED"
    INSPECTION = "INSPECTION"
    DECISION = "DECISION"
    COMMAND_SENT = "COMMAND_SENT"
    OPERATOR_OVERRIDE = "OPERATOR_OVERRIDE"
    ERROR = "ERROR"
    SYSTEM_STATUS = "SYSTEM_STATUS"


class FactoryEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_type: EventType
    agent: str = "system"
    data: dict[str, Any] = Field(default_factory=dict)
    source_document: str = ""
    source_location: dict[str, Any] = Field(default_factory=dict)


class ShiftStats(BaseModel):
    total_inspected: int = 0
    passed: int = 0
    rejected: int = 0
    manual_reviews: int = 0
    operator_overrides: int = 0
    pass_rate: float = 0.0
    avg_confidence: float = 0.0
    start_time: datetime | None = None
    end_time: datetime | None = None


# ---------------------------------------------------------------------------
# WebSocket Events
# ---------------------------------------------------------------------------

class WSEventType(str, Enum):
    INSPECTION = "inspection"
    DECISION = "decision"
    COMMAND = "command"
    ERROR = "error"
    POLICY_UPDATE = "policy_update"
    STATUS = "status"
    OPERATOR_REQUEST = "operator_request"
    FACTORY_FLOOR = "factory_floor"


class WSEvent(BaseModel):
    type: WSEventType
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Factory Floor Animation Events
# ---------------------------------------------------------------------------

class FactoryFloorEvent(BaseModel):
    animation: Literal["PICK", "PLACE", "MOVE", "STOP", "INSPECT"] = "PLACE"
    target: str | None = None
    part_id: str | None = None
    part_color: str | None = None
    status: Literal["OK", "ERROR"] = "OK"


# ---------------------------------------------------------------------------
# API Request/Response Models
# ---------------------------------------------------------------------------

class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    pages: int
    tables_found: int
    sections: list[str]
    parse_time_ms: float


class PolicyApprovalRequest(BaseModel):
    operator_id: str = "operator-1"


class InspectRequest(BaseModel):
    use_camera: bool = True
    image_base64: str | None = None


class OperatorOverrideRequest(BaseModel):
    part_id: str
    override_bin: str
    reason: str = ""
    operator_id: str = "operator-1"


class QARequest(BaseModel):
    question: str


class QAResponse(BaseModel):
    answer: str
    sources: list[DocumentSource] = Field(default_factory=list)
    events_referenced: list[str] = Field(default_factory=list)
