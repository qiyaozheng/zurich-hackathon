"use client";

import { InspectionResult } from "../lib/types";

interface EventLogProps {
  events: InspectionResult[];
  onSelectEvent: (event: InspectionResult) => void;
}

export default function EventLog({ events, onSelectEvent }: EventLogProps) {
  return (
    <div className="border-t" style={{ borderColor: "var(--color-border)" }}>
      <div className="flex items-center justify-between px-6 py-2">
        <span className="text-[10px] uppercase tracking-widest" style={{ color: "var(--color-text-muted)" }}>
          Inspection Log
        </span>
        {events.length > 0 && (
          <span className="text-[10px] tabular-nums" style={{ color: "var(--color-text-muted)" }}>
            {events.length} events
          </span>
        )}
      </div>

      <div className="overflow-y-auto max-h-[160px]">
        {events.length === 0 ? (
          <div className="px-6 py-4 text-center">
            <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--color-text-muted)" }}>
              No inspections yet
            </div>
            <div className="text-[10px] mt-1" style={{ color: "var(--color-border)" }}>
              Upload a document and approve a policy to begin
            </div>
          </div>
        ) : (
          <div>
            <div
              className="flex items-center gap-4 px-6 py-1 text-[9px] uppercase tracking-widest border-b"
              style={{ color: "var(--color-text-muted)", borderColor: "var(--color-border)" }}
            >
              <span className="w-16">Time</span>
              <span className="w-14">Part</span>
              <span className="w-4" />
              <span className="w-20">Class</span>
              <span className="w-1" />
              <span className="w-20">Target</span>
              <span className="w-14">Rule</span>
              <span className="w-10 text-right">Conf</span>
            </div>
            {events.map((ev, i) => {
              const ts = new Date(ev.timestamp).toLocaleTimeString("en-GB", { hour12: false });
              const isReject = ev.decision.action === "REJECT";

              return (
                <div
                  key={i}
                  onClick={() => onSelectEvent(ev)}
                  className="flex items-center gap-4 px-6 py-1.5 cursor-pointer border-b text-xs transition-colors"
                  style={{ borderColor: "var(--color-border)" }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--color-surface-2)")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                >
                  <span className="w-16 tabular-nums" style={{ color: "var(--color-text-muted)" }}>
                    {ts}
                  </span>
                  <span className="w-14 font-medium">{ev.part_id.replace("part-", "#")}</span>
                  <span
                    className="w-3 h-3 inline-block border"
                    style={{
                      backgroundColor: ev.classification.color_hex,
                      borderColor: "var(--color-border)",
                    }}
                  />
                  <span className="w-20 truncate">
                    {ev.classification.color} {ev.classification.size_mm}mm
                  </span>
                  <span style={{ color: "var(--color-accent-green)" }}>→</span>
                  <span
                    className="w-20 font-bold"
                    style={{ color: isReject ? "var(--color-accent-red)" : "var(--color-text)" }}
                  >
                    {ev.decision.target_bin}
                  </span>
                  <span className="w-14" style={{ color: "var(--color-text-muted)" }}>
                    {ev.decision.rule_id}
                  </span>
                  <span className="w-10 text-right tabular-nums" style={{ color: "var(--color-text-muted)" }}>
                    {(ev.classification.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
