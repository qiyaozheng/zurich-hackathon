"use client";

import { InspectionResult } from "../lib/types";

interface DoclingTraceViewProps {
  event: InspectionResult | null;
  onClose: () => void;
}

export default function DoclingTraceView({ event, onClose }: DoclingTraceViewProps) {
  if (!event) return null;

  const source = event.decision.source;

  return (
    <>
      <div
        className="fixed inset-0 z-40"
        style={{ background: "rgba(0,0,0,0.5)" }}
        onClick={onClose}
      />
      <div
        className="fixed right-0 top-0 h-full w-[380px] border-l p-6 overflow-y-auto z-50"
        style={{
          borderColor: "var(--color-border)",
          background: "var(--color-bg)",
        }}
      >
        <div className="flex items-center justify-between mb-6">
          <span className="text-[10px] uppercase tracking-widest" style={{ color: "var(--color-text-muted)" }}>
            Document Traceability
          </span>
          <button
            onClick={onClose}
            className="text-xs px-2 py-1 border transition-colors hover:bg-[var(--color-surface-2)]"
            style={{ borderColor: "var(--color-border)", color: "var(--color-text-muted)" }}
          >
            ESC
          </button>
        </div>

        <Section title="Part">
          <KV label="ID" value={event.part_id} />
          <KV label="Time" value={new Date(event.timestamp).toLocaleTimeString("en-GB")} />
        </Section>

        <Section title="Classification">
          <div className="flex items-center gap-2 mb-1">
            <span
              className="w-4 h-4 inline-block border"
              style={{ backgroundColor: event.classification.color_hex, borderColor: "var(--color-border)" }}
            />
            <span className="text-xs font-medium">{event.classification.color.toUpperCase()}</span>
          </div>
          <KV label="Type" value={event.classification.part_type} />
          <KV label="Size" value={`${event.classification.size_mm}mm (${event.classification.size_category})`} />
          <KV label="Shape" value={event.classification.shape} />
          <KV label="Confidence" value={`${(event.classification.confidence * 100).toFixed(1)}%`} />
        </Section>

        <Section title="Defect Inspection">
          <KV
            label="Status"
            value={event.defect_inspection.defect_detected ? "DEFECT DETECTED" : "PASS"}
            color={event.defect_inspection.defect_detected ? "var(--color-accent-red)" : "var(--color-accent-green)"}
          />
          <KV label="Surface" value={event.defect_inspection.surface_quality.toUpperCase()} />
          {event.defect_inspection.defects.map((d, i) => (
            <div key={i} className="border-l-2 pl-3 ml-1 mt-2 space-y-0.5" style={{ borderColor: "var(--color-accent-red)" }}>
              <div className="text-xs font-medium" style={{ color: "var(--color-accent-red)" }}>
                {d.type.toUpperCase()}
              </div>
              <KV label="Severity" value={d.severity} />
              <KV label="Location" value={d.location} />
              <KV label="Confidence" value={`${(d.confidence * 100).toFixed(0)}%`} />
            </div>
          ))}
        </Section>

        <Section title="Decision">
          <KV label="Action" value={event.decision.action} />
          <KV label="Target" value={event.decision.target_bin} />
          <KV label="Rule" value={event.decision.rule_id} />
          <div className="mt-1 p-2 border text-[11px]" style={{ borderColor: "var(--color-border)", background: "var(--color-surface)", fontFamily: "var(--font-mono)" }}>
            {event.decision.rule_condition || "—"}
          </div>
        </Section>

        {source && (
          <Section title="Document Source">
            <KV label="Document" value={source.document_name} />
            <KV label="Page" value={source.page.toString()} />
            <KV label="Section" value={source.section} />
            {source.table_id && <KV label="Table" value={source.table_id} />}
            {source.row !== undefined && source.row !== null && <KV label="Row" value={source.row.toString()} />}
            {source.cell_text && (
              <div
                className="mt-2 p-3 border text-[11px]"
                style={{ borderColor: "var(--color-accent-yellow)", background: "var(--color-surface)" }}
              >
                <div className="text-[9px] uppercase tracking-widest mb-1" style={{ color: "var(--color-accent-yellow)" }}>
                  Source Text
                </div>
                {source.cell_text}
              </div>
            )}
            {source.bbox && (
              <KV label="Bbox" value={source.bbox.map((n) => n.toFixed(0)).join(", ")} />
            )}
          </Section>
        )}

        {event.decision.requires_operator && (
          <div
            className="mt-4 p-3 border"
            style={{ borderColor: "var(--color-accent-yellow)", background: "rgba(255,204,0,0.05)" }}
          >
            <div className="text-[10px] uppercase tracking-widest font-bold" style={{ color: "var(--color-accent-yellow)" }}>
              Operator Review Required
            </div>
            <div className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
              Confidence below threshold. Verify decision before proceeding.
            </div>
          </div>
        )}
      </div>
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-5">
      <div
        className="text-[10px] uppercase tracking-widest mb-2 pb-1 border-b"
        style={{ color: "var(--color-text-muted)", borderColor: "var(--color-border)" }}
      >
        {title}
      </div>
      <div className="space-y-1">{children}</div>
    </div>
  );
}

function KV({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex justify-between text-xs">
      <span style={{ color: "var(--color-text-muted)" }}>{label}</span>
      <span className="font-medium" style={color ? { color } : undefined}>
        {value}
      </span>
    </div>
  );
}
