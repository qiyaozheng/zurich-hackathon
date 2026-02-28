"use client";

import { useState } from "react";
import { InspectionResult } from "../lib/types";

interface CameraFeedProps {
  lastResult: InspectionResult | null;
  onInspect: () => void;
  isInspecting: boolean;
  policyActive: boolean;
}

export default function CameraFeed({ lastResult, onInspect, isInspecting, policyActive }: CameraFeedProps) {
  const r = lastResult;
  const [streamError, setStreamError] = useState(false);

  return (
    <div className="flex flex-col">
      <div className="text-[10px] uppercase tracking-widest mb-2" style={{ color: "var(--color-text-muted)" }}>
        Camera Feed
      </div>

      <div
        className="relative border overflow-hidden"
        style={{ borderColor: "var(--color-border)", background: "#000", aspectRatio: "4/3", maxHeight: "200px" }}
      >
        {!streamError ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src="http://localhost:8000/camera/stream"
            alt="Live camera feed"
            className="w-full h-full object-cover"
            onError={() => setStreamError(true)}
          />
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
            <span className="text-lg" style={{ color: "var(--color-text-muted)" }}>◉</span>
            <span className="text-[10px] uppercase tracking-widest" style={{ color: "var(--color-text-muted)" }}>
              No Camera
            </span>
            <button
              onClick={() => setStreamError(false)}
              className="text-[10px] border px-2 py-0.5 mt-1"
              style={{ borderColor: "var(--color-border)", color: "var(--color-text-muted)" }}
            >
              Retry
            </button>
          </div>
        )}

        {isInspecting && (
          <div className="absolute inset-0 flex items-center justify-center" style={{ background: "rgba(0,0,0,0.5)" }}>
            <div className="border-2 w-16 h-16 animate-pulse" style={{ borderColor: "var(--color-accent-green)" }} />
          </div>
        )}
      </div>

      {r && (
        <div className="mt-3 space-y-1">
          <Row label="TYPE" value={r.classification.part_type.toUpperCase()} />
          <Row label="COLOR" value={r.classification.color.toUpperCase()} color={r.classification.color_hex} />
          <Row label="SIZE" value={`${r.classification.size_mm}mm`} />
          <Row
            label="DEFECT"
            value={r.defect_inspection.defect_detected ? "DETECTED" : "NONE"}
            color={r.defect_inspection.defect_detected ? "var(--color-accent-red)" : "var(--color-accent-green)"}
          />
          <Row label="CONF" value={(r.classification.confidence * 100).toFixed(0) + "%"} />

          <div className="border-t pt-2 mt-2" style={{ borderColor: "var(--color-border)" }}>
            <div className="flex items-center gap-2">
              <span className="text-[10px] uppercase tracking-widest" style={{ color: "var(--color-text-muted)" }}>
                Decision
              </span>
              <span className="flex-1" />
              <span style={{ color: "var(--color-accent-green)" }}>→</span>
              <span className="font-bold text-sm">{r.decision.target_bin}</span>
            </div>
            <div className="text-[10px] mt-1" style={{ color: "var(--color-text-muted)" }}>
              {r.decision.rule_id}
              {r.decision.source && ` · p${r.decision.source.page} · ${r.decision.source.section}`}
            </div>
          </div>
        </div>
      )}

      <button
        onClick={onInspect}
        disabled={isInspecting || !policyActive}
        className="mt-3 w-full py-2.5 text-[10px] uppercase tracking-widest border font-bold transition-colors"
        style={{
          borderColor: !policyActive
            ? "var(--color-border)"
            : isInspecting
              ? "var(--color-accent-yellow)"
              : "var(--color-accent-green)",
          color: !policyActive
            ? "var(--color-text-muted)"
            : isInspecting
              ? "var(--color-accent-yellow)"
              : "var(--color-accent-green)",
          background: "transparent",
          cursor: !policyActive ? "not-allowed" : "pointer",
        }}
      >
        {!policyActive ? "Approve Policy to Inspect" : isInspecting ? "Inspecting..." : "Inspect"}
      </button>
    </div>
  );
}

function Row({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex justify-between text-xs">
      <span style={{ color: "var(--color-text-muted)" }}>{label}</span>
      <span className="font-medium tabular-nums" style={color ? { color } : undefined}>
        {value}
      </span>
    </div>
  );
}
