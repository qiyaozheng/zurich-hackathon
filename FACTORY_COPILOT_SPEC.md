# Havoc — Document-Driven Factory Intelligence

> Documents don't get read — they get run. Docling parses factory SOPs, DeepMind compiles them into executable policy, Vision AI inspects real parts live, a simulated factory floor shows where every part goes — and when a real robot plugs in, it just works.

---

## System Principles

1. **Docling is the entry point** — every rule originates from a parsed document.
2. **DeepMind is the policy brain** — compiles documents into decision policies, resolves ambiguity, generates vision prompts.
3. **Vision AI is the eyes** — classification, defect detection, verification — all camera-based, all live.
4. **Robot-ready by design** — full command pipeline exists, currently targeting a visual simulator, swappable to real robot via one adapter change.
5. **Full traceability** — every decision traces back to document → page → table → cell.
6. **Docling full lifecycle** — documents IN (parse SOPs) AND documents OUT (generate reports).

---

## Architecture: LangChain Multi-Agent System

Five specialized agents coordinated by a LangGraph Supervisor.

```
                              ┌─────────────────────┐
                              │   SupervisorAgent    │
                              │   (LangGraph)        │
                              └──────────┬──────────┘
                    ┌──────────┬─────────┼─────────┬──────────┐
                    ▼          ▼         ▼         ▼          ▼
             ┌───────────┐ ┌────────┐ ┌────────┐ ┌─────────┐ ┌──────────┐
             │ Document  │ │ Policy │ │ Vision │ │Execution│ │ Report   │
             │ Agent     │ │ Agent  │ │ Agent  │ │ Agent   │ │ Agent    │
             │ (Docling) │ │(Gemini)│ │(Gemini)│ │(Adapter)│ │(Docling) │
             └───────────┘ └────────┘ └────────┘ └─────────┘ └──────────┘
                  │             │          │           │            │
               Docling      Policy     Camera     Simulator     Docling
               Parse +      Store      + Gemini   or Robot     Generate
               MCP Server              Vision     (TCP)
```

### Agent Responsibilities

| Agent | Role | Tools |
|---|---|---|
| **DocumentAgent** | Parse factory docs via Docling, extract rules/tolerances/safety | `docling_convert`, `docling_extract_tables`, `docling_get_sections` |
| **PolicyAgent** | Compile extracted data into executable policy, validate, diff | `compile_policy`, `validate_policy`, `diff_policies`, `resolve_conflicts` |
| **VisionAgent** | Classify parts, detect defects, verify state — all via camera | `capture_image`, `classify_part`, `inspect_defects` |
| **ExecutionAgent** | Send commands to robot adapter (simulator or real), enforce safety | `adapter_pick`, `adapter_place`, `adapter_move`, `adapter_stop`, `preflight` |
| **ReportAgent** | Generate shift reports via Docling, answer operator Q&A | `docling_create_doc`, `docling_add_section`, `query_events`, `explain_decision` |

### Supervisor (LangGraph)

```python
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent

gemini = ChatGoogleGenerativeAI(model="gemini-2.5-pro")

def create_supervisor():
    workflow = StateGraph(FactoryState)
    
    workflow.add_node("document_agent", document_agent)
    workflow.add_node("policy_agent", policy_agent)
    workflow.add_node("vision_agent", vision_agent)
    workflow.add_node("execution_agent", execution_agent)
    workflow.add_node("report_agent", report_agent)
    workflow.add_node("supervisor", supervisor_decide)
    
    workflow.add_conditional_edges("supervisor", route_to_agent, {
        "document": "document_agent",
        "policy": "policy_agent",
        "vision": "vision_agent",
        "execution": "execution_agent",
        "report": "report_agent",
        "done": END
    })
    
    for agent in ["document_agent", "policy_agent", "vision_agent",
                   "execution_agent", "report_agent"]:
        workflow.add_edge(agent, "supervisor")
    
    workflow.set_entry_point("supervisor")
    return workflow.compile()
```

### Data Flow

```
DOCUMENT FLOW:
  PDF → DocumentAgent (Docling) → PolicyAgent (compile) → Human Approval → Policy Store

INSPECTION FLOW:
  Operator places part → VisionAgent (classify + defect) → PolicyAgent (decide) 
  → ExecutionAgent (command to adapter) → HMI shows result + virtual floor animation

REPORT FLOW:
  Event Log → ReportAgent → Docling Generation → PDF/Markdown Report

OPERATOR Q&A FLOW:
  Operator question → ReportAgent → Event Log + Policy + Document → Contextual answer
```

---

## Step 1: Document Ingestion (Docling)

Docling parses factory documents into a unified `DoclingDocument` — structured JSON with tables, text, images, formulas, reading order, bounding boxes. Runs 100% locally.

**Install:** `pip install docling`

**Supported inputs:** PDF, DOCX, PPTX, XLSX, HTML, images (PNG, JPEG, TIFF), scanned docs (OCR).

| Document Element | Docling Feature | Output |
|---|---|---|
| Sorting tables | Table structure recognition (TableFormer) | Rows, columns, headers, cell content |
| Tolerance specs | Formula recognition (LaTeX) | Numeric thresholds |
| Process flowcharts | Image classification + layout analysis | Diagram type + bounding boxes |
| Quality criteria | Text extraction + reading order | Structured text sections |
| Safety limits | Text extraction | Constraint parameters |
| Scanned pages | OCR engine | Digitized text |

### Python API

```python
from docling.document_converter import DocumentConverter

converter = DocumentConverter()
result = converter.convert("documents/sorting_procedure_v3.pdf")
doc = result.document

markdown = doc.export_to_markdown()   # → for DeepMind agent
doc_dict = doc.export_to_dict()       # → full structured JSON

for table in doc.tables:
    df = table.export_to_dataframe()  # → pandas DataFrame
```

### Docling MCP Server (for agentic access)

```json
{
  "mcpServers": {
    "docling": {
      "command": "uvx",
      "args": ["--from=docling-mcp", "docling-mcp-server"]
    }
  }
}
```

MCP tools: conversion (PDF → DoclingDocument), generation (create new docs, add sections, export), RAG (optional).

### What the PolicyAgent receives (Markdown from Docling)

```markdown
## Sorting Criteria

| Part Type | Color | Size Range (mm) | Target Bin |
|-----------|-------|-----------------|------------|
| Type A    | red   | >50             | BIN_A      |
| Type B    | blue  | 30-50           | BIN_B      |
| Type C    | green | <30             | BIN_C      |
| Defective | any   | any             | REJECT     |

## Quality Inspection

Parts with visible surface defects, cracks, or discoloration must be rejected.

## Safety Constraints

Maximum robot speed during sorting: 80%. Grip force must not exceed 15N.
```

---

## Step 2: DeepMind Policy Agent

The brain. Takes Docling output, reasons about it, compiles executable policy.

| Task | Input | Output |
|---|---|---|
| Rule compilation | Docling tables + text | Structured decision policy |
| Ambiguity resolution | "small parts" → what size? | Resolved thresholds from context |
| Conflict detection | Overlapping rules | Flagged conflicts + resolution |
| Edge case handling | What if no rule matches? | Default actions + confidence thresholds |
| Vision prompt generation | Quality criteria text | Gemini Vision inspection prompts |
| Policy diffing | Old doc vs new doc | Change report + updated policy |

**Compiled Policy:**
```json
{
  "policy_id": "policy-20260228-001",
  "source_document": "sorting_procedure_v3.pdf",
  "version": 3,

  "vision_instructions": {
    "classify": {
      "prompt": "Analyze this part. Determine: 1) dominant color (red/blue/green/other), 2) size estimate in mm, 3) any visible defects (cracks, discoloration, surface damage). Return JSON.",
      "model": "gemini-2.5-pro"
    }
  },

  "decision_rules": [
    {"id": "RULE_001", "priority": 1, "condition": "defect_detected == true", "action": "REJECT", "target_bin": "REJECT_BIN", "source": {"page": 5, "section": "Quality Inspection"}},
    {"id": "RULE_002", "priority": 2, "condition": "confidence < 0.7", "action": "MANUAL_REVIEW", "target_bin": "REVIEW_BIN", "source": {"page": 6, "section": "Decision Tree"}},
    {"id": "RULE_003", "priority": 3, "condition": "color == 'red' AND size_mm > 50", "action": "SORT", "target_bin": "BIN_A", "source": {"page": 3, "table": "Table 2.1", "row": 1}},
    {"id": "RULE_004", "priority": 4, "condition": "color == 'blue' AND size_mm >= 30 AND size_mm <= 50", "action": "SORT", "target_bin": "BIN_B", "source": {"page": 3, "table": "Table 2.1", "row": 2}},
    {"id": "RULE_005", "priority": 5, "condition": "color == 'green' AND size_mm < 30", "action": "SORT", "target_bin": "BIN_C", "source": {"page": 3, "table": "Table 2.1", "row": 3}}
  ],

  "default_action": {"action": "MANUAL_REVIEW", "target_bin": "REVIEW_BIN"},

  "safety_constraints": {"max_speed_pct": 80, "max_grip_force_n": 15, "source": {"page": 7}},

  "execution_sequence": ["VISION_CLASSIFY", "POLICY_DECIDE", "ROUTE_TO_BIN", "VERIFY"]
}
```

---

## Step 3: Vision AI (Camera-Based, Live)

Everything the system "sees" goes through Gemini Vision. The inspection prompts come FROM the parsed document.

### Part Classification + Defect Detection

```python
import google.generativeai as genai
from PIL import Image

model = genai.GenerativeModel("gemini-2.5-pro")

async def inspect_part(image: Image, policy: SortingPolicy) -> dict:
    """Single vision call: classify + defect detect using document-derived prompt."""
    
    response = await model.generate_content_async([
        policy.vision_instructions["classify"]["prompt"],
        image
    ])
    
    return {
        "color": response.color,
        "size_mm": response.size_mm,
        "defect_detected": response.defect_detected,
        "defect_type": response.defect_type,
        "confidence": response.confidence
    }
```

**Key insight:** The vision prompt comes FROM the document. SOP says "reject parts with cracks or discoloration" → DeepMind compiles that into a vision prompt. Change the document → change what the camera looks for.

### Camera Setup

```python
import cv2
from PIL import Image

class Camera:
    def __init__(self, device_id: int = 0):
        self.cap = cv2.VideoCapture(device_id)
    
    def capture(self) -> Image:
        ret, frame = self.cap.read()
        if not ret:
            raise CameraError("No frame")
        return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    
    def get_frame_base64(self) -> str:
        ret, frame = self.cap.read()
        _, buffer = cv2.imencode('.jpg', frame)
        return base64.b64encode(buffer).decode('utf-8')
```

---

## Step 4: Robot Adapter Pattern (Simulator Now, Real Robot Later)

The system generates full robot commands. Today they go to a visual simulator on the HMI. Tomorrow they go to a real robot via TCP. ONE line change.

```python
from abc import ABC, abstractmethod

class RobotAdapter(ABC):
    @abstractmethod
    def pick(self) -> dict: ...
    @abstractmethod
    def place(self, bin_id: str) -> dict: ...
    @abstractmethod
    def move(self, position: str) -> dict: ...
    @abstractmethod
    def stop(self) -> dict: ...
    @abstractmethod
    def heartbeat(self) -> dict: ...

class SimulatorAdapter(RobotAdapter):
    """Sends commands to HMI virtual factory floor via WebSocket."""
    
    def __init__(self, websocket):
        self.ws = websocket
    
    def pick(self) -> dict:
        self.ws.send_json({"animation": "PICK", "status": "OK"})
        return {"status": "OK", "adapter": "simulator"}
    
    def place(self, bin_id: str) -> dict:
        self.ws.send_json({"animation": "PLACE", "target": bin_id, "status": "OK"})
        return {"status": "OK", "adapter": "simulator", "bin": bin_id}
    
    def move(self, position: str) -> dict:
        self.ws.send_json({"animation": "MOVE", "position": position})
        return {"status": "OK"}
    
    def stop(self) -> dict:
        self.ws.send_json({"animation": "STOP"})
        return {"status": "STOPPED"}
    
    def heartbeat(self) -> dict:
        return {"status": "OK", "adapter": "simulator"}

class TCPRobotAdapter(RobotAdapter):
    """Sends commands to real robot via TCP. Plug-and-play."""
    
    def __init__(self, host: str, port: int):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))
    
    def _send(self, command: str) -> dict:
        self.sock.sendall(f"{command}\n".encode())
        return json.loads(self.sock.recv(1024).decode().strip())
    
    def pick(self) -> dict:
        return self._send("PICK")
    
    def place(self, bin_id: str) -> dict:
        return self._send(f"PLACE_{bin_id}")
    
    def move(self, position: str) -> dict:
        return self._send(f"MOVE_{position}")
    
    def stop(self) -> dict:
        return self._send("EMERGENCY_STOP")
    
    def heartbeat(self) -> dict:
        return self._send("HEARTBEAT")

# Switch between simulator and real robot:
# adapter = SimulatorAdapter(websocket)     # ← Hackathon demo
# adapter = TCPRobotAdapter("192.168.1.10", 5000)  # ← Real robot
```

**Why this matters for judges:** "We built a complete robotic system. The intelligence is all here — document parsing, policy compilation, vision inspection, command generation. Today we demo with simulation. To connect a real robot, we change one line. That's engineering maturity, not a hack."

---

## Step 5: Inspection Loop (Complete with Safety)

```python
async def inspection_loop(adapter: RobotAdapter, vision: Camera, policy: SortingPolicy, hmi: HMI):
    """Main loop — operator places parts, system inspects and decides."""
    
    # Preflight
    preflight = await run_preflight(adapter, vision, policy)
    if not preflight.passed:
        await hmi.show_error(f"Preflight failed: {preflight.failures}")
        return
    
    await hmi.show_status("RUNNING")
    
    while True:
        if hmi.pause_requested:
            await hmi.show_status("PAUSED")
            await hmi.wait_for_resume()
            continue
        
        try:
            # 1. Capture
            image = vision.capture()
            if image is None:
                await hmi.alert("Camera feed lost")
                await hmi.wait_for_resume()
                continue
            
            # 2. Vision AI inspect (classify + defect)
            result = await inspect_part(image, policy)
            
            # 3. Confidence gate
            if result["confidence"] < 0.3:
                decision = policy.default_action
                await hmi.alert(f"Very low confidence ({result['confidence']:.0%})")
            elif result["confidence"] < 0.7:
                operator_input = await hmi.ask_operator(
                    f"Low confidence ({result['confidence']:.0%}). "
                    f"Classified: {result['color']}, {result['size_mm']}mm. "
                    f"Suggested: {policy.evaluate(result).target_bin}",
                    options=["ACCEPT", "OVERRIDE", "SKIP"]
                )
                if operator_input.action == "SKIP":
                    decision = Decision(target_bin="REVIEW_BIN", rule="OPERATOR_SKIP")
                elif operator_input.action == "OVERRIDE":
                    decision = Decision(target_bin=operator_input.override_bin, rule="OPERATOR_OVERRIDE")
                else:
                    decision = policy.evaluate(result)
            else:
                # 4. Policy decision
                decision = policy.evaluate(result)
            
            # 5. Execute (simulator animation or real robot)
            adapter.place(decision.target_bin)
            
            # 6. Log with full traceability
            emit_event(InspectionEvent(
                classification=result,
                decision=decision,
                source_rule=decision.source,
                source_document=policy.source_doc
            ))
            
            # 7. Update HMI
            await hmi.update(result, decision)
        
        except VisionError as e:
            await hmi.alert(f"Vision error: {e}")
            await hmi.wait_for_resume()
        except Exception as e:
            adapter.stop()
            await hmi.alert(f"Error: {e}")
            await hmi.wait_for_resume()
```

---

## The Killer Feature: Document Change → Behavior Change

```
BEFORE: sorting_procedure_v3.pdf
  Rule: red parts > 50mm → BIN_A
  System inspects red 48mm part → BIN_B (too small for BIN_A)

UPLOAD: sorting_procedure_v4.pdf  
  Changed: red parts > 45mm → BIN_A (threshold lowered)
  
  DeepMind detects change, recompiles policy
  System now routes red 48mm part → BIN_A ✅
  NO CODE CHANGES. Document drove the change.
```

**Policy Diff (auto-generated):**
```json
{
  "diff_type": "RULE_MODIFIED",
  "rule_id": "RULE_003",
  "old_value": "color == 'red' AND size_mm > 50",
  "new_value": "color == 'red' AND size_mm > 45",
  "source_old": {"document": "v3.pdf", "page": 3, "table": "2.1"},
  "source_new": {"document": "v4.pdf", "page": 3, "table": "2.1"},
  "impact": "Parts 45-50mm now go to BIN_A instead of BIN_B"
}
```

---

## Human-in-the-Loop Safety

### Policy Approval Gate

No policy goes live without human approval.

```
Document uploaded → Docling parses → DeepMind compiles → HUMAN REVIEW
                                                              │
                                                   [APPROVE] [REJECT] [EDIT]
```

Policy states: `DRAFT` → `APPROVED` → `SUSPENDED` (or `REJECTED`)

### Completeness Validation

| Missing Element | Severity | Behavior |
|---|---|---|
| No sorting rules extracted | CRITICAL | Cannot approve |
| No safety constraints | CRITICAL | Cannot approve |
| No default action | HIGH | DeepMind adds MANUAL_REVIEW default |
| Low rule coverage (< 50%) | HIGH | Operator must acknowledge |
| Unparsed sections | MEDIUM | Flagged for review |

### Confidence Gates (Per-Inspection)

```
Confidence ≥ 0.7  → Autonomous decision
Confidence < 0.7  → PAUSE, ask operator
Confidence < 0.3  → Flag anomaly, default to REVIEW
```

### Operator Controls

| Action | Effect |
|---|---|
| PAUSE | System pauses after current inspection |
| OVERRIDE | Operator manually assigns bin |
| SKIP | Part goes to REVIEW bin |
| SUSPEND POLICY | Policy deactivated |
| ADJUST CONFIDENCE | Change threshold live (slider) |

Every override logged with operator ID + timestamp.

---

## Docling Report Generation (Document In → Document Out)

The system doesn't just READ documents — it WRITES them. Full Docling lifecycle.

**Docling MCP Generation Tools:**
```
create_new_docling_document       → Start new report
add_title_to_docling_document     → Title
add_heading_to_docling_document   → Section headings
add_paragraph_to_docling_document → Content
open_list_in_docling_document     → Start list
add_listitem_to_list              → List items
close_list_in_docling_document    → Close list
export_docling_document_to_markdown → Export
save_docling_document             → Save file
```

**Shift Report Example:**
```markdown
# Shift Report — 2026-02-28, 06:00–14:00

## Summary
- Parts inspected: 342
- Passed: 330 (96.5%)
- Rejected: 12 (3.5%)
- Manual reviews: 5
- Operator overrides: 2

## Anomalies
1. Part #187 — low confidence (0.42), operator overrode to BIN_A
   Source: RULE_003, p3, Table 2.1
2. Part #291 — crack detected, rejected per RULE_001
   Source: p5, Quality Inspection

## Recommendations
- 3 "yellow" parts had no matching rule → update SOP
- Confidence dropped in hour 6 → check lighting
```

---

## Operator Q&A (Contextual, Not Chatbot)

Operator asks questions on HMI. ReportAgent answers with document traceability.

**"Why was part #41 rejected?"**
> Part #41 rejected: surface crack detected (confidence 0.91). Matches RULE_001 from sorting_procedure_v3.pdf, page 5, "Quality Inspection": "Parts with visible surface defects must be rejected."

**"What changed between v3 and v4?"**
> 3 changes: 1) RULE_003 threshold 50mm→45mm (p3, Table 2.1), 2) New RULE_006 for yellow→BIN_D, 3) Max speed 80%→85% (p7).

**"How many red parts this shift?"**
> 127 red parts → BIN_A. All matched RULE_003. Avg confidence: 0.89.

---

## Multi-Document Handling

| Document | Provides | Example |
|---|---|---|
| Sorting SOP | Sorting rules, decision trees | "Red > 50mm → BIN_A" |
| Machine Spec | Safety limits, speed constraints | "Max speed: 80%" |
| Quality Manual | Defect definitions, criteria | "Crack = REJECT" |
| Part Catalog | Expected dimensions, types | "Type A: 40-70mm" |

Cross-document conflicts auto-detected:
```json
{
  "conflict": "SPEED_LIMIT_MISMATCH",
  "doc_a": {"file": "sop_v3.pdf", "page": 7, "value": "max 80%"},
  "doc_b": {"file": "machine_spec.pdf", "page": 12, "value": "max 70%"},
  "resolution": "Using stricter limit (70%). Operator must confirm.",
  "requires_human": true
}
```

---

## Error Handling

| Failure | Response | Recovery |
|---|---|---|
| Camera feed lost | PAUSE, alert operator | Operator checks, resumes |
| Vision AI timeout | Retry 1x → PAUSE | Part → REVIEW |
| Vision returns garbage | Schema validation fail → PAUSE | Part → REVIEW |
| Docling parse failure | Policy stays DRAFT | Operator reviews raw doc |
| DeepMind compilation error | Policy stays DRAFT | Retry or manual edit |
| Adapter disconnected | PAUSE | Auto-reconnect, operator confirms |

**Principle:** System always fails to SAFE state. Nothing happens without human confirmation after error.


---

## HMI — Operator Dashboard with Virtual Factory Floor

Next.js web app running on localhost. The operator's single screen for everything.

### Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│  Havoc — Factory Copilot                             [PAUSE] [STOP]  │
├──────────────────────┬───────────────────────────────────────────────┤
│                      │                                               │
│   LIVE CAMERA FEED   │         VIRTUAL FACTORY FLOOR                │
│   ┌──────────────┐   │   ┌─────────────────────────────────────┐    │
│   │              │   │   │                                     │    │
│   │   (webcam)   │   │   │   [CAMERA]──→ ─ ─ ─ ┐              │    │
│   │              │   │   │                      ▼              │    │
│   └──────────────┘   │   │              ┌──────────────┐       │    │
│                      │   │              │  INSPECTION  │       │    │
│   Classification:    │   │              └──────┬───────┘       │    │
│   Color: RED         │   │         ┌───────┬───┴───┬───────┐  │    │
│   Size: 52mm         │   │         ▼       ▼       ▼       ▼  │    │
│   Confidence: 94%    │   │      [BIN_A] [BIN_B] [BIN_C] [REJ] │    │
│   Defects: None      │   │       (12)    (8)     (5)    (2)  │    │
│                      │   │                                     │    │
│   Decision: BIN_A    │   └─────────────────────────────────────┘    │
│   Rule: RULE_003     │                                               │
│   Source: p3, T2.1   │   Part count animation: dots flow from       │
│                      │   camera → inspection → target bin           │
├──────────────────────┴───────────────────────────────────────────────┤
│  POLICY: sorting_v3.pdf (APPROVED)  │  Parts: 342  Pass: 96.5%     │
├─────────────────────────────────────┴────────────────────────────────┤
│  EVENT LOG (live scroll)                                             │
│  14:02:31  Part #342  RED 52mm → BIN_A  (RULE_003, conf: 0.94)     │
│  14:02:18  Part #341  BLUE 35mm → BIN_B  (RULE_004, conf: 0.88)    │
│  14:01:55  Part #340  GREEN 22mm → BIN_C  (RULE_005, conf: 0.91)   │
├──────────────────────────────────────────────────────────────────────┤
│  OPERATOR Q&A: [Why was part #340 sent to BIN_C?___________] [ASK]  │
└──────────────────────────────────────────────────────────────────────┘
```

### Virtual Factory Floor

The animated 2D visualization shows the physical layout of the sorting station. When the system decides where a part goes, the virtual floor animates it in real time via WebSocket.

```typescript
// HMI receives WebSocket events from SimulatorAdapter
interface FactoryFloorEvent {
  animation: "PICK" | "PLACE" | "MOVE" | "STOP";
  target?: string;       // BIN_A, BIN_B, etc.
  partId?: string;
  status: "OK" | "ERROR";
}

// On each event → animate a dot from inspection zone to target bin
// Bins show running count, color-coded by part type
// Rejected parts flash red
```

**Why this matters:** Other teams without a robot will show a terminal. We show a live animated factory floor where you SEE parts being routed. Judges see a working system, not a log dump.

---

## Event Sourcing & Audit Trail

Every action in the system is an immutable event. Full traceability from document to decision.

```python
@dataclass
class FactoryEvent:
    event_id: str           # UUID
    timestamp: datetime
    event_type: str         # DOCUMENT_PARSED, POLICY_COMPILED, INSPECTION, DECISION, COMMAND, ERROR
    agent: str              # Which agent produced this
    data: dict              # Event-specific payload
    source_document: str    # Originating document
    source_location: dict   # Page, table, section reference

# Stored in SQLite — lightweight, no setup
events_db = sqlite3.connect("events.db")
```

**Event Types:**

| Event | Trigger | Data |
|---|---|---|
| `DOCUMENT_PARSED` | Docling finishes | doc_id, pages, tables_found, parse_time |
| `POLICY_COMPILED` | DeepMind compiles | policy_id, rules_count, conflicts |
| `POLICY_APPROVED` | Operator approves | policy_id, operator_id |
| `INSPECTION` | Vision AI result | part_id, classification, confidence, defects |
| `DECISION` | Policy evaluation | part_id, rule_id, target_bin, source_ref |
| `COMMAND_SENT` | Adapter command | command_type, adapter_type, target |
| `OPERATOR_OVERRIDE` | Manual override | part_id, original_bin, override_bin, reason |
| `ERROR` | Any failure | error_type, component, recovery_action |

Every report, every Q&A answer, every decision traces back through this chain.

---

## Tech Stack & Deployment

Everything runs on localhost. No cloud dependency. No Docker required for demo.

| Layer | Technology | Why |
|---|---|---|
| Backend | Python 3.11 + FastAPI | Async, fast, LangChain native |
| Multi-Agent | LangChain + LangGraph | Supervisor pattern, tool binding |
| Document AI | Docling (local) | IBM track requirement, full lifecycle |
| LLM | Gemini 2.5 Pro (API) | Vision + reasoning, single model |
| Vision | OpenCV + Gemini Vision | Camera capture + AI inspection |
| HMI | Next.js (React) | Virtual factory floor, live updates |
| Real-time | WebSocket (FastAPI ↔ Next.js) | Live camera, events, animations |
| Database | SQLite | Event store, policy store, zero setup |
| Document Gen | Docling MCP | Report generation (doc out) |

### API Keys Required

```env
GOOGLE_API_KEY=your-gemini-api-key
```

That's it. Everything else is local.

### Run Commands

```bash
# Terminal 1: Backend
pip install fastapi uvicorn langchain langchain-google-genai langgraph docling opencv-python pillow
uvicorn main:app --reload --port 8000

# Terminal 2: HMI
cd hmi
npm install
npm run dev
# → http://localhost:3000

# Terminal 3 (optional): Docling MCP Server
uvx --from=docling-mcp docling-mcp-server
```

---

## Project Structure

```
havoc/
├── main.py                    # FastAPI app, WebSocket, routes
├── config.py                  # Settings, API keys, adapter selection
├── models.py                  # Pydantic models (Policy, Event, Decision)
│
├── agents/
│   ├── supervisor.py          # LangGraph supervisor + state
│   ├── document_agent.py      # Docling parsing + extraction
│   ├── policy_agent.py        # DeepMind policy compilation
│   ├── vision_agent.py        # Camera + Gemini Vision
│   ├── execution_agent.py     # Robot adapter commands
│   └── report_agent.py        # Docling report gen + Q&A
│
├── tools/
│   ├── docling_tools.py       # Docling convert, extract, generate
│   ├── vision_tools.py        # Camera capture, classify, inspect
│   ├── policy_tools.py        # Compile, validate, diff
│   └── adapter_tools.py       # Pick, place, move, stop
│
├── adapters/
│   ├── base.py                # RobotAdapter ABC
│   ├── simulator.py           # SimulatorAdapter (WebSocket → HMI)
│   └── tcp_robot.py           # TCPRobotAdapter (real robot)
│
├── store/
│   ├── event_store.py         # SQLite event sourcing
│   └── policy_store.py        # Policy CRUD + versioning
│
├── documents/                 # Upload folder for factory SOPs
│
├── hmi/                       # Next.js frontend
│   ├── package.json
│   ├── app/
│   │   ├── page.tsx           # Main dashboard
│   │   ├── components/
│   │   │   ├── CameraFeed.tsx
│   │   │   ├── FactoryFloor.tsx    # Animated virtual floor
│   │   │   ├── EventLog.tsx
│   │   │   ├── PolicyPanel.tsx
│   │   │   ├── OperatorQA.tsx
│   │   │   └── InspectionResult.tsx
│   │   └── lib/
│   │       └── websocket.ts   # WS client
│   └── public/
│
├── events.db                  # SQLite (auto-created)
└── README.md
```

---

## 24h Build Plan

| Hour | Task | Owner | Deliverable |
|---|---|---|---|
| 0–2 | Project setup, FastAPI scaffold, models, config | Backend | Running server, models defined |
| 0–2 | Next.js scaffold, layout, WebSocket client | Frontend | HMI shell with live WS |
| 2–4 | DocumentAgent + Docling integration | Backend | PDF → parsed markdown/tables |
| 2–4 | Camera feed component, live stream to HMI | Frontend | Webcam visible on dashboard |
| 4–6 | PolicyAgent + DeepMind compilation | Backend | Document → compiled policy JSON |
| 4–6 | Virtual Factory Floor animation | Frontend | Animated bins, part routing dots |
| 6–8 | VisionAgent + Gemini Vision classify/defect | Backend | Camera → classification result |
| 6–8 | InspectionResult + PolicyPanel components | Frontend | Live results on HMI |
| 8–10 | ExecutionAgent + SimulatorAdapter + WebSocket | Backend | Decisions → HMI animations |
| 8–10 | EventLog + Operator controls (pause/override) | Frontend | Full operator interaction |
| 10–12 | LangGraph Supervisor wiring, full pipeline test | Backend | End-to-end: doc → vision → sort |
| 12–14 | ReportAgent + Docling report generation | Backend | Shift report PDF/MD output |
| 12–14 | Operator Q&A component | Frontend | Ask questions, get traced answers |
| 14–16 | Policy diff (upload v4, see changes) | Backend | Document change → behavior change |
| 14–16 | Policy approval UI, confidence slider | Frontend | Human-in-the-loop on HMI |
| 16–18 | Multi-document handling, conflict detection | Backend | Cross-doc conflict resolution |
| 16–18 | Full integration testing, edge cases | Both | Stable demo flow |
| 18–20 | Error handling, safety gates, preflight | Backend | Bulletproof failure modes |
| 18–20 | Polish HMI, animations, responsive layout | Frontend | Demo-ready UI |
| 20–22 | Demo script rehearsal, bug fixes | Both | Smooth 5-min demo |
| 22–24 | Buffer, final polish, README | Both | Ship it |

**Priority if behind schedule:** Cut multi-doc and report gen. Core pipeline (doc → policy → vision → sort → HMI) is the must-have.

---

## Demo Script (5 minutes)

| # | Action | What Judges See | Time |
|---|---|---|---|
| 1 | Upload `sorting_procedure_v3.pdf` | Docling parses, tables extracted, markdown shown | 0:00 |
| 2 | DeepMind compiles policy | Policy JSON appears, rules listed, vision prompts generated | 0:30 |
| 3 | Operator reviews + approves policy | Approval gate UI, policy goes ACTIVE | 0:45 |
| 4 | Place a RED part in front of camera | Live camera feed, Gemini Vision classifies: red, 52mm, no defects | 1:00 |
| 5 | System decides → BIN_A | Decision shown with rule ID + document source (page, table, row) | 1:15 |
| 6 | Virtual factory floor animates | Dot flows from camera → inspection → BIN_A, counter increments | 1:30 |
| 7 | Place a CRACKED part | Vision detects defect → REJECT bin, red flash on virtual floor | 2:00 |
| 8 | Place AMBIGUOUS part (low confidence) | System pauses, asks operator, operator overrides → logged | 2:30 |
| 9 | Upload `sorting_procedure_v4.pdf` | DeepMind diffs: "threshold changed 50→45mm", recompiles policy | 3:00 |
| 10 | Same red 48mm part → now goes to BIN_A | Document changed behavior. No code change. | 3:30 |
| 11 | Ask Q&A: "Why was part #7 rejected?" | Traced answer with document reference | 4:00 |
| 12 | Generate shift report | Docling creates report document — full lifecycle demo | 4:15 |
| 13 | Show adapter swap (1 line) | "To connect a real robot: change SimulatorAdapter → TCPRobotAdapter" | 4:30 |

---

## Why This Wins

1. **Full Docling lifecycle** — Documents IN (parse SOPs) AND documents OUT (generate reports). No other team will do both.
2. **Document drives behavior** — Change the PDF, change what the system does. Not a chatbot. Not reformatting. Actual execution logic changes.
3. **Vision is real** — Live camera, real parts, Gemini Vision. Physical-digital bridging that judges can see.
4. **Virtual Factory Floor** — While others show terminals, we show an animated factory. Parts flow visually. Judges understand instantly.
5. **Robot-ready architecture** — Full command pipeline exists. Adapter pattern means one line to connect real hardware. That's engineering, not a hack.
6. **Multi-Agent with traceability** — Every decision traces back to document → page → table → cell. Auditable. Industrial-grade.
7. **Human-in-the-loop** — Safety gates, confidence thresholds, operator override. Not a black box.
8. **Handles messy docs** — Multi-document, cross-doc conflicts, scanned pages, OCR. Real-world ready.
