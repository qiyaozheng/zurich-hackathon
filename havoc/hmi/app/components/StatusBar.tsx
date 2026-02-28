"use client";

import { useEffect, useState } from "react";

interface StatusBarProps {
  status: string;
  policyName: string | null;
  onStop: () => void;
}

interface SystemStatus {
  camera: boolean;
  camera_backend: string;
  ws_clients: number;
  part_counter: number;
}

const API = "http://localhost:8000";

export default function StatusBar({ status, policyName, onStop }: StatusBarProps) {
  const [sys, setSys] = useState<SystemStatus | null>(null);

  useEffect(() => {
    const poll = () => {
      fetch(`${API}/status`)
        .then((r) => r.json())
        .then(setSys)
        .catch(() => setSys(null));
    };
    poll();
    const id = setInterval(poll, 5000);
    return () => clearInterval(id);
  }, []);

  const alive = sys !== null;
  const statusColor =
    status === "RUNNING"
      ? "var(--color-accent-green)"
      : status === "STOPPED"
        ? "var(--color-accent-red)"
        : "var(--color-text-muted)";

  return (
    <div
      className="flex items-center justify-between px-6 py-3 border-b"
      style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }}
    >
      <div className="flex items-center gap-8">
        <div className="flex items-baseline gap-3">
          <span className="text-xl font-bold tracking-tight">HAVOC</span>
          <span className="text-[10px] uppercase tracking-[0.2em]" style={{ color: "var(--color-text-muted)" }}>
            Document Execution Engine
          </span>
        </div>

        <div className="flex items-center gap-4 text-[10px] uppercase tracking-widest" style={{ color: "var(--color-text-muted)" }}>
          <Indicator label="API" on={alive} />
          <Indicator label="CAM" on={sys?.camera ?? false} detail={sys?.camera_backend} />
          <Indicator label="WS" on={(sys?.ws_clients ?? 0) > 0} detail={sys?.ws_clients?.toString()} />
        </div>
      </div>

      <div className="flex items-center gap-6">
        {policyName && (
          <div className="flex items-center gap-2">
            <span className="text-[10px] uppercase tracking-widest" style={{ color: "var(--color-text-muted)" }}>
              Policy
            </span>
            <span className="text-xs font-medium">{policyName}</span>
          </div>
        )}

        {sys?.part_counter !== undefined && sys.part_counter > 0 && (
          <span className="text-xs tabular-nums" style={{ color: "var(--color-text-muted)" }}>
            {sys.part_counter} inspected
          </span>
        )}

        <div className="flex items-center gap-2">
          <span className="inline-block w-1.5 h-1.5" style={{ backgroundColor: statusColor, borderRadius: "50%" }} />
          <span className="text-[10px] uppercase tracking-widest">{status}</span>
        </div>

        <button
          onClick={onStop}
          className="px-3 py-1 text-[10px] uppercase tracking-widest border transition-colors hover:bg-[var(--color-accent-red)] hover:text-black"
          style={{
            borderColor: "var(--color-accent-red)",
            color: "var(--color-accent-red)",
            background: "transparent",
          }}
        >
          STOP
        </button>
      </div>
    </div>
  );
}

function Indicator({ label, on, detail }: { label: string; on: boolean; detail?: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span
        className="inline-block w-1 h-1"
        style={{ backgroundColor: on ? "var(--color-accent-green)" : "var(--color-accent-red)", borderRadius: "50%" }}
      />
      <span>{label}</span>
      {detail && on && <span style={{ color: "var(--color-text)" }}>{detail}</span>}
    </span>
  );
}
