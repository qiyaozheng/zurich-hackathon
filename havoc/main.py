"""Havoc — Document Execution Engine. FastAPI backend."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from config import settings
from models import (
    Decision,
    DocumentUploadResponse,
    EventType,
    ExecutablePolicy,
    FactoryEvent,
    InspectRequest,
    InspectionResult,
    OperatorOverrideRequest,
    PolicyApprovalRequest,
    PolicyStatus,
    QARequest,
    QAResponse,
    WSEvent,
    WSEventType,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("havoc")


# ---------------------------------------------------------------------------
# WebSocket Connection Manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._connections:
            self._connections.remove(ws)

    async def broadcast(self, data: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def broadcast_event(self, event_type: WSEventType, data: dict[str, Any]) -> None:
        event = WSEvent(type=event_type, data=data)
        await self.broadcast(event.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# Global State
# ---------------------------------------------------------------------------

class AppState:
    def __init__(self):
        self.event_store = None
        self.policy_store = None
        self.adapter = None
        self.camera = None
        self.supervisor = None
        self.connection_manager = ConnectionManager()
        self.part_counter: int = 0
        self.parsed_documents: dict[str, Any] = {}
        self.system_status: str = "INITIALIZING"
        self.confidence_threshold: float = settings.confidence_high


state = AppState()


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    from store.event_store import EventStore
    from store.policy_store import PolicyStore
    from adapters.simulator import SimulatorAdapter
    from adapters.dual import create_adapter
    from tools.vision_tools import Camera
    from agents.report_agent import set_stores

    state.event_store = EventStore(settings.sqlite_path)
    await state.event_store.init()

    state.policy_store = PolicyStore(settings.sqlite_path)
    await state.policy_store.init()

    set_stores(state.event_store, state.policy_store)

    sim = SimulatorAdapter()
    sim.set_broadcast(state.connection_manager.broadcast)

    state.adapter = create_adapter(
        dobot_host=settings.dobot_host,
        dobot_port=settings.dobot_port,
        simulator=sim,
    )
    from tools.robot_functions import set_robot_backend
    set_robot_backend(state.adapter, state.connection_manager.broadcast)

    state.camera = Camera(
        device_id=settings.camera_device_id,
        width=settings.camera_width,
        height=settings.camera_height,
        fps=settings.camera_fps,
        camera_type=settings.camera_type,
        ws_url=settings.camera_ws_url,
    )
    state.camera.open()

    if settings.camera_type == "websocket" and settings.camera_ws_url:
        await state.camera.start_ws_receiver()

    settings.documents_dir.mkdir(parents=True, exist_ok=True)

    state.system_status = "READY"
    logger.info("Havoc backend started — %s (orchestrator: %s)", "READY", settings.gemini_orchestrator_model)

    yield

    state.system_status = "SHUTDOWN"
    if state.camera:
        state.camera.release()
    if state.event_store:
        await state.event_store.close()
    if state.policy_store:
        await state.policy_store.close()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Havoc — Document Execution Engine", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.responses import JSONResponse
from starlette.requests import Request

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": str(exc)})


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await state.connection_manager.connect(ws)
    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        state.connection_manager.disconnect(ws)


# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------

@app.get("/camera/stream")
async def camera_stream():
    if not state.camera or not state.camera.is_open():
        raise HTTPException(503, "Camera not available")
    return StreamingResponse(
        state.camera.generate_mjpeg(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/camera/snapshot")
async def camera_snapshot():
    if not state.camera or not state.camera.is_open():
        raise HTTPException(503, "Camera not available")
    b64 = state.camera.capture_base64()
    if not b64:
        raise HTTPException(503, "Failed to capture frame")
    return {"image_base64": b64}


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

@app.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)):
    filename = file.filename or f"upload-{uuid.uuid4().hex[:8]}"
    doc_id = str(uuid.uuid4())
    dest = settings.documents_dir / filename

    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    logger.info("Document saved: %s → %s", filename, dest)

    from tools.docling_tools import parse_document_full

    try:
        parsed = await asyncio.to_thread(parse_document_full, dest)
    except Exception as e:
        logger.error("Docling parse failed: %s", e, exc_info=True)
        raise HTTPException(500, f"Document parsing failed: {e}")

    parsed.document_id = doc_id
    state.parsed_documents[doc_id] = parsed

    await state.event_store.emit(FactoryEvent(
        event_type=EventType.DOCUMENT_PARSED,
        agent="document_agent",
        data={
            "document_id": doc_id,
            "filename": filename,
            "pages": parsed.pages,
            "tables_found": parsed.tables_found,
            "sections": parsed.sections,
            "parse_time_ms": parsed.parse_time_ms,
        },
        source_document=filename,
    ))

    await state.connection_manager.broadcast_event(
        WSEventType.STATUS,
        {"message": f"Document parsed: {filename}", "document_id": doc_id},
    )

    return DocumentUploadResponse(
        document_id=doc_id,
        filename=filename,
        pages=parsed.pages,
        tables_found=parsed.tables_found,
        sections=parsed.sections,
        parse_time_ms=parsed.parse_time_ms,
    )


@app.get("/documents")
async def list_documents():
    return {
        doc_id: {
            "filename": p.filename,
            "format": p.format,
            "pages": p.pages,
            "tables_found": p.tables_found,
            "sections": p.sections,
        }
        for doc_id, p in state.parsed_documents.items()
    }


@app.get("/documents/{doc_id}/markdown")
async def get_document_markdown(doc_id: str):
    if doc_id not in state.parsed_documents:
        raise HTTPException(404, "Document not found")
    return {"markdown": state.parsed_documents[doc_id].markdown}


@app.get("/documents/{doc_id}/tables")
async def get_document_tables(doc_id: str):
    if doc_id not in state.parsed_documents:
        raise HTTPException(404, "Document not found")
    return {"tables": state.parsed_documents[doc_id].tables_data}


# ---------------------------------------------------------------------------
# Policy Compilation (via Supervisor)
# ---------------------------------------------------------------------------

@app.post("/policies/compile/{doc_id}")
async def compile_policy(doc_id: str):
    if doc_id not in state.parsed_documents:
        raise HTTPException(404, "Document not found")

    parsed = state.parsed_documents[doc_id]

    try:
        from agents.supervisor import create_havoc_supervisor
        supervisor = create_havoc_supervisor()

        result = await asyncio.to_thread(
            supervisor.invoke,
            {"messages": [{
                "role": "user",
                "content": (
                    f"Parse and compile a policy from this document: {parsed.filename}\n\n"
                    f"Document content:\n{parsed.markdown[:6000]}\n\n"
                    f"Tables found: {json.dumps(parsed.tables_data[:5], default=str)}\n\n"
                    "Compile this into an ExecutablePolicy JSON with decision_rules, "
                    "safety_constraints, inspection_criteria, and vision_instructions."
                ),
            }]},
        )

        last_msg = result["messages"][-1].content if result.get("messages") else ""

        try:
            start = last_msg.find("{")
            end = last_msg.rfind("}") + 1
            if start >= 0 and end > start:
                policy_data = json.loads(last_msg[start:end])
                policy = ExecutablePolicy(**policy_data)
            else:
                policy = _build_fallback_policy(parsed)
        except Exception:
            policy = _build_fallback_policy(parsed)

    except Exception as e:
        logger.warning("Supervisor compilation failed: %s — using fallback", e)
        policy = _build_fallback_policy(parsed)

    from models import DocumentSource
    policy.source_documents = [DocumentSource(
        document_id=doc_id,
        document_name=parsed.filename,
    )]

    await state.policy_store.store(policy)

    await state.event_store.emit(FactoryEvent(
        event_type=EventType.POLICY_COMPILED,
        agent="policy_agent",
        data={
            "policy_id": policy.policy_id,
            "rules_count": len(policy.decision_rules),
            "safety_count": len(policy.safety_constraints),
            "status": policy.status.value,
        },
        source_document=parsed.filename,
    ))

    await state.connection_manager.broadcast_event(
        WSEventType.POLICY_UPDATE,
        {"policy": policy.model_dump(mode="json")},
    )

    return policy.model_dump(mode="json")


def _build_fallback_policy(parsed) -> ExecutablePolicy:
    """Build a reasonable default policy from parsed document data."""
    from models import (
        DecisionRule, DefaultAction, DocumentSource, InspectionCriterion,
        SafetyConstraint, VisionPrompt,
    )

    rules = [
        DecisionRule(id="RULE_001", priority=1, condition="defect_detected == true", action="REJECT", target_bin="REJECT_BIN"),
        DecisionRule(id="RULE_002", priority=2, condition="confidence < 0.7", action="MANUAL_REVIEW", target_bin="REVIEW_BIN"),
        DecisionRule(id="RULE_003", priority=3, condition="color == 'red' AND size_mm > 50", action="SORT", target_bin="BIN_A"),
        DecisionRule(id="RULE_004", priority=4, condition="color == 'blue' AND size_mm >= 30 AND size_mm <= 50", action="SORT", target_bin="BIN_B"),
        DecisionRule(id="RULE_005", priority=5, condition="color == 'green' AND size_mm < 30", action="SORT", target_bin="BIN_C"),
    ]

    for r in rules:
        r.source = DocumentSource(document_id="", document_name=parsed.filename, page=1, section="Sorting Criteria")

    return ExecutablePolicy(
        decision_rules=rules,
        safety_constraints=[
            SafetyConstraint(id="SAFETY_001", parameter="speed_pct", operator="<=", value=80, unit="%"),
            SafetyConstraint(id="SAFETY_002", parameter="grip_force_n", operator="<=", value=15, unit="N"),
        ],
        inspection_criteria=[
            InspectionCriterion(id="IC_001", description="Surface defect check", check_type="visual", action_on_fail="REJECT"),
        ],
        vision_instructions={
            "classify": VisionPrompt(
                prompt="Analyze this factory part. Determine: 1) dominant color (red/blue/green/yellow/other), 2) size estimate in mm, 3) shape (round/square/irregular). Be precise.",
                mode="classify",
            ),
            "defect": VisionPrompt(
                prompt="Inspect this part for defects: cracks, scratches, discoloration, dents, chips, contamination. Rate surface quality.",
                mode="defect",
            ),
        },
        default_action=DefaultAction(),
    )


# ---------------------------------------------------------------------------
# Policy Management
# ---------------------------------------------------------------------------

@app.get("/policies")
async def list_policies():
    policies = await state.policy_store.list_all()
    return [p.model_dump(mode="json") for p in policies]


@app.get("/policies/active")
async def get_active_policy():
    p = state.policy_store.active_policy
    if not p:
        raise HTTPException(404, "No active policy")
    return p.model_dump(mode="json")


@app.post("/policies/{policy_id}/approve")
async def approve_policy(policy_id: str, req: PolicyApprovalRequest):
    policy = await state.policy_store.approve(policy_id)
    if not policy:
        raise HTTPException(404, "Policy not found")

    await state.event_store.emit(FactoryEvent(
        event_type=EventType.POLICY_APPROVED,
        agent="operator",
        data={"policy_id": policy_id, "operator_id": req.operator_id},
    ))

    await state.connection_manager.broadcast_event(
        WSEventType.POLICY_UPDATE,
        {"policy": policy.model_dump(mode="json"), "action": "approved"},
    )
    return {"status": "approved", "policy_id": policy_id}


@app.post("/policies/{policy_id}/reject")
async def reject_policy(policy_id: str):
    policy = await state.policy_store.reject(policy_id)
    if not policy:
        raise HTTPException(404, "Policy not found")
    return {"status": "rejected", "policy_id": policy_id}


# ---------------------------------------------------------------------------
# Inspection Pipeline (direct — no supervisor)
# ---------------------------------------------------------------------------

@app.post("/inspect")
async def inspect_part(req: InspectRequest | None = None):
    policy = state.policy_store.active_policy
    if not policy:
        raise HTTPException(400, "No active policy — upload and approve a document first")

    state.part_counter += 1
    part_id = f"part-{state.part_counter:04d}"

    image = None
    if req and req.image_base64:
        import base64
        from io import BytesIO
        from PIL import Image as PILImage
        img_bytes = base64.b64decode(req.image_base64)
        image = PILImage.open(BytesIO(img_bytes))
    elif state.camera and state.camera.is_open():
        image = state.camera.capture()

    if image is None:
        raise HTTPException(503, "No image available — camera not connected and no image provided")

    from agents.orchestrator import orchestrate_inspection
    result = await orchestrate_inspection(
        image, policy, part_id=part_id,
        broadcast_fn=state.connection_manager.broadcast,
    )

    confidence = result.classification.confidence
    if confidence < state.confidence_threshold and confidence >= settings.confidence_low:
        result.decision.requires_operator = True

    await state.event_store.emit(FactoryEvent(
        event_type=EventType.INSPECTION,
        agent="vision_agent",
        data={
            "part_id": part_id,
            "color": result.classification.color,
            "size_mm": result.classification.size_mm,
            "defect_detected": result.defect_inspection.defect_detected,
            "confidence": confidence,
            "action": result.decision.action,
            "target_bin": result.decision.target_bin,
            "rule_id": result.decision.rule_id,
        },
        source_document=policy.source_documents[0].document_name if policy.source_documents else "",
        source_location=result.decision.source.model_dump() if result.decision.source else {},
    ))

    await state.connection_manager.broadcast_event(
        WSEventType.INSPECTION,
        result.model_dump(mode="json"),
    )

    return result.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Operator Controls
# ---------------------------------------------------------------------------

@app.post("/operator/override")
async def operator_override(req: OperatorOverrideRequest):
    await state.adapter.place(req.override_bin)

    await state.event_store.emit(FactoryEvent(
        event_type=EventType.OPERATOR_OVERRIDE,
        agent="operator",
        data={
            "part_id": req.part_id,
            "override_bin": req.override_bin,
            "reason": req.reason,
            "operator_id": req.operator_id,
        },
    ))

    await state.connection_manager.broadcast_event(
        WSEventType.DECISION,
        {"part_id": req.part_id, "override_bin": req.override_bin, "action": "OPERATOR_OVERRIDE"},
    )
    return {"status": "overridden", "bin": req.override_bin}


@app.post("/operator/confidence")
async def set_confidence(threshold: float):
    state.confidence_threshold = max(0.0, min(1.0, threshold))
    return {"confidence_threshold": state.confidence_threshold}


# ---------------------------------------------------------------------------
# Q&A
# ---------------------------------------------------------------------------

@app.post("/qa", response_model=QAResponse)
async def operator_qa(req: QARequest):
    try:
        from agents.supervisor import create_havoc_supervisor
        supervisor = create_havoc_supervisor()

        result = await asyncio.to_thread(
            supervisor.invoke,
            {"messages": [{"role": "user", "content": req.question}]},
        )

        answer = result["messages"][-1].content if result.get("messages") else "No answer available"
        return QAResponse(answer=answer)
    except Exception as e:
        logger.error("Q&A failed: %s", e)
        return QAResponse(answer=f"Error processing question: {str(e)}")


# ---------------------------------------------------------------------------
# Task Orchestration (Gemini Robotics-ER free-form tasks)
# ---------------------------------------------------------------------------

from pydantic import BaseModel as _BaseModel

class OrchestrateRequest(_BaseModel):
    task: str
    use_camera: bool = True


@app.post("/orchestrate")
async def orchestrate_task(req: OrchestrateRequest):
    """Execute a free-form task using Gemini Robotics-ER 1.5."""
    image = None
    if req.use_camera and state.camera and state.camera.is_open():
        image = state.camera.capture()

    policy = state.policy_store.active_policy if state.policy_store else None

    from agents.orchestrator import orchestrate_free_task
    result = await orchestrate_free_task(
        task=req.task,
        image=image,
        policy=policy,
        broadcast_fn=state.connection_manager.broadcast,
    )

    await state.event_store.emit(FactoryEvent(
        event_type=EventType.COMMAND_SENT,
        agent="orchestrator",
        data={
            "task": req.task,
            "steps": len(result.get("steps", [])),
            "summary": result.get("summary", "")[:500],
        },
    ))

    await state.connection_manager.broadcast_event(
        WSEventType.STATUS,
        {"message": f"Task completed: {req.task}", "steps": len(result.get("steps", []))},
    )

    return result


# ---------------------------------------------------------------------------
# Events & Stats
# ---------------------------------------------------------------------------

@app.get("/events")
async def get_events(limit: int = 50):
    events = await state.event_store.get_recent(limit=limit)
    return [e.model_dump(mode="json") for e in events]


@app.get("/stats")
async def get_stats():
    stats = await state.event_store.get_stats()
    return stats.model_dump(mode="json")


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------

@app.get("/status")
async def system_status():
    return {
        "status": state.system_status,
        "camera": state.camera.is_open() if state.camera else False,
        "camera_backend": state.camera._backend if state.camera else "none",
        "orchestrator_model": settings.gemini_orchestrator_model,
        "active_policy": state.policy_store.active_policy.policy_id if state.policy_store and state.policy_store.active_policy else None,
        "part_counter": state.part_counter,
        "confidence_threshold": state.confidence_threshold,
        "ws_clients": len(state.connection_manager._connections),
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
