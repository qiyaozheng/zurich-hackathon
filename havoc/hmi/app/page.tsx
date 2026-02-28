"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { HavocWebSocket } from "./lib/websocket";
import { ExecutablePolicy, InspectionResult, WSEvent } from "./lib/types";
import StatusBar from "./components/StatusBar";
import CameraFeed from "./components/CameraFeed";
import FactoryFloor from "./components/FactoryFloor";
import EventLog from "./components/EventLog";
import PolicyPanel from "./components/PolicyPanel";
import OperatorQA from "./components/OperatorQA";
import DoclingTraceView from "./components/DoclingTraceView";

const API = "http://localhost:8000";

export default function Dashboard() {
  const [status, setStatus] = useState("READY");
  const [policy, setPolicy] = useState<ExecutablePolicy | null>(null);
  const [events, setEvents] = useState<InspectionResult[]>([]);
  const [lastResult, setLastResult] = useState<InspectionResult | null>(null);
  const [isInspecting, setIsInspecting] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<InspectionResult | null>(null);
  const [lastAnimation, setLastAnimation] = useState<{ target?: string; part_color?: string } | null>(null);
  const [bins, setBins] = useState([
    { id: "BIN_A", count: 0, color: "#FF3333" },
    { id: "BIN_B", count: 0, color: "#3388FF" },
    { id: "BIN_C", count: 0, color: "#00FF66" },
    { id: "REJECT_BIN", count: 0, color: "#FF3333" },
  ]);
  const [stats, setStats] = useState({ total: 0, passRate: 0, avgConf: 0 });

  const wsRef = useRef<HavocWebSocket | null>(null);

  useEffect(() => {
    const ws = new HavocWebSocket();
    wsRef.current = ws;
    ws.connect();

    const unsub = ws.onEvent((event: WSEvent) => {
      if (event.type === "inspection") {
        const result = event.data as unknown as InspectionResult;
        setLastResult(result);
        setEvents((prev) => [result, ...prev].slice(0, 200));
        setStatus("RUNNING");

        setBins((prev) =>
          prev.map((b) =>
            b.id === result.decision.target_bin ? { ...b, count: b.count + 1 } : b
          )
        );
        setStats((prev) => {
          const total = prev.total + 1;
          const rejected = result.decision.action === "REJECT" ? 1 : 0;
          const passed = total - rejected;
          return {
            total,
            passRate: passed / total,
            avgConf: (prev.avgConf * prev.total + result.classification.confidence) / total,
          };
        });

        setLastAnimation({
          target: result.decision.target_bin,
          part_color: result.classification.color_hex,
        });
      }

      if (event.type === "policy_update") {
        const data = event.data as { policy?: ExecutablePolicy };
        if (data.policy) setPolicy(data.policy);
      }

      if (event.type === "factory_floor") {
        const data = event.data as { target?: string; part_color?: string };
        setLastAnimation(data);
      }
    });

    fetch(`${API}/policies/active`)
      .then((r) => (r.ok ? r.json() : null))
      .then((p) => {
        if (p) setPolicy(p);
      })
      .catch(() => {});

    return () => {
      unsub();
      ws.disconnect();
    };
  }, []);

  const handleUpload = useCallback(async (file: File) => {
    const form = new FormData();
    form.append("file", file);

    try {
      const res = await fetch(`${API}/documents/upload`, { method: "POST", body: form });
      if (!res.ok) {
        console.error("Upload failed:", await res.text());
        return;
      }
      const doc = await res.json();

      const compileRes = await fetch(`${API}/policies/compile/${doc.document_id}`, { method: "POST" });
      if (compileRes.ok) {
        const compiled = await compileRes.json();
        setPolicy(compiled);
      }
    } catch (e) {
      console.error("Upload failed:", e);
    }
  }, []);

  const handleApprove = useCallback(async (policyId: string) => {
    try {
      await fetch(`${API}/policies/${policyId}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ operator_id: "operator-1" }),
      });
      setPolicy((prev) => (prev ? { ...prev, status: "APPROVED" } : prev));
      setStatus("RUNNING");
    } catch (e) {
      console.error("Approve failed:", e);
    }
  }, []);

  const handleReject = useCallback(async (policyId: string) => {
    try {
      await fetch(`${API}/policies/${policyId}/reject`, { method: "POST" });
      setPolicy((prev) => (prev ? { ...prev, status: "REJECTED" } : prev));
    } catch (e) {
      console.error("Reject failed:", e);
    }
  }, []);

  const handleInspect = useCallback(async () => {
    setIsInspecting(true);
    try {
      const res = await fetch(`${API}/inspect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ use_camera: true }),
      });
      if (!res.ok) {
        console.error("Inspect failed:", await res.text());
      }
    } catch (e) {
      console.error("Inspect failed:", e);
    }
    setIsInspecting(false);
  }, []);

  const handleQA = useCallback(async (question: string): Promise<string> => {
    const res = await fetch(`${API}/qa`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const data = await res.json();
    return data.answer || "No answer";
  }, []);

  const handleStop = useCallback(() => {
    setStatus("STOPPED");
  }, []);

  const policyActive = policy?.status === "APPROVED";

  return (
    <div className="h-screen flex flex-col" style={{ background: "var(--color-bg)" }}>
      <StatusBar
        status={status}
        policyName={
          policy ? `${policy.source_documents?.[0]?.document_name || policy.policy_id}` : null
        }
        onStop={handleStop}
      />

      <div className="flex-1 flex overflow-hidden">
        <div
          className="w-[320px] border-r flex flex-col overflow-y-auto shrink-0"
          style={{ borderColor: "var(--color-border)" }}
        >
          <PolicyPanel
            policy={policy}
            onUpload={handleUpload}
            onApprove={handleApprove}
            onReject={handleReject}
          />
          <div className="p-4">
            <CameraFeed
              lastResult={lastResult}
              onInspect={handleInspect}
              isInspecting={isInspecting}
              policyActive={policyActive}
            />
          </div>
        </div>

        <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
          <div className="p-4 h-[360px] shrink-0">
            <FactoryFloor
              bins={bins}
              totalInspected={stats.total}
              passRate={stats.passRate}
              avgConfidence={stats.avgConf}
              lastAnimation={lastAnimation}
            />
          </div>

          <EventLog events={events} onSelectEvent={setSelectedEvent} />
          <OperatorQA onAsk={handleQA} />
        </div>
      </div>

      <DoclingTraceView event={selectedEvent} onClose={() => setSelectedEvent(null)} />
    </div>
  );
}
