# HAVOC — Document Execution Engine

> Documents don't get read — they get run.

Upload any factory document. Docling parses it. Gemini compiles it into executable policy. Vision AI inspects parts. The robot sorts them. Change the document — change the behavior. Zero code changes.

## Quick Start

### 1. Backend

```bash
cd havoc
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your GOOGLE_API_KEY
uvicorn main:app --reload --port 8000
```

### 2. Frontend

```bash
cd havoc/hmi
npm install
npm run dev
```

Open http://localhost:3000

### 3. Demo Flow

1. Upload `sorting_procedure_v3.md` (or PDF/DOCX)
2. System parses via Docling, compiles policy via Gemini
3. Approve the policy
4. Click INSPECT — camera captures, Gemini classifies, robot sorts
5. Upload `sorting_procedure_v4.md` — thresholds change, behavior changes
6. Upload `machine_spec.md` — cross-document conflict detected

## Architecture

```
Document (PDF/DOCX/Image)
  → Docling (TableFormer, OCR, Layout Analysis)
  → Gemini (Policy Compilation)
  → Human Approval
  → Vision AI (Classify + Defect Detect)
  → Rule Engine (Safe evaluation)
  → Robot Adapter (Dobot CR / Simulator)
  → HMI (Swiss Brutalism Dashboard)
```

**Hybrid Architecture:**
- LangGraph Supervisor for document/report flows (multi-step reasoning)
- Direct async pipeline for inspection (sub-3s latency)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python + FastAPI |
| Multi-Agent | LangChain + LangGraph |
| Document AI | Docling (local) |
| LLM | Gemini 2.5 Pro |
| Vision | OpenCV + Gemini Vision |
| Robot | Dobot CR (TCP/IP) + Simulator |
| Frontend | Next.js + Tailwind |
| Database | SQLite (WAL mode) |
| Real-time | WebSocket |

## API Keys

```env
GOOGLE_API_KEY=your-gemini-api-key
```

That's it. Everything else is local.
