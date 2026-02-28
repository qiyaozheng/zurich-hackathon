"use client";

import { useCallback, useState } from "react";

interface Message {
  role: "user" | "assistant";
  text: string;
  time: string;
}

interface OperatorQAProps {
  onAsk: (question: string) => Promise<string>;
}

export default function OperatorQA({ onAsk }: OperatorQAProps) {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);

  const handleAsk = useCallback(async () => {
    if (!question.trim() || loading) return;
    const q = question.trim();
    setQuestion("");
    setLoading(true);

    const now = new Date().toLocaleTimeString("en-GB", { hour12: false });
    setMessages((prev) => [...prev, { role: "user", text: q, time: now }]);

    try {
      const result = await onAsk(q);
      const ansTime = new Date().toLocaleTimeString("en-GB", { hour12: false });
      setMessages((prev) => [...prev, { role: "assistant", text: result, time: ansTime }]);
    } catch {
      const errTime = new Date().toLocaleTimeString("en-GB", { hour12: false });
      setMessages((prev) => [...prev, { role: "assistant", text: "Error processing question", time: errTime }]);
    }
    setLoading(false);
  }, [question, loading, onAsk]);

  return (
    <div className="border-t" style={{ borderColor: "var(--color-border)" }}>
      {messages.length > 0 && (
        <div className="max-h-[120px] overflow-y-auto px-6 py-2 space-y-2">
          {messages.map((m, i) => (
            <div key={i} className="flex gap-2 text-xs">
              <span className="shrink-0 tabular-nums" style={{ color: "var(--color-text-muted)" }}>
                {m.time}
              </span>
              <span
                className="shrink-0 w-3"
                style={{ color: m.role === "user" ? "var(--color-accent-blue)" : "var(--color-accent-green)" }}
              >
                {m.role === "user" ? ">" : "<"}
              </span>
              <span className={m.role === "assistant" ? "" : ""} style={m.role === "user" ? { color: "var(--color-text-muted)" } : {}}>
                {m.text}
              </span>
            </div>
          ))}
          {loading && (
            <div className="flex gap-2 text-xs">
              <span className="shrink-0 tabular-nums" style={{ color: "var(--color-text-muted)" }}>
                {""}
              </span>
              <span className="shrink-0 w-3" style={{ color: "var(--color-accent-green)" }}>{"<"}</span>
              <span className="animate-pulse" style={{ color: "var(--color-text-muted)" }}>thinking...</span>
            </div>
          )}
        </div>
      )}

      <div className="flex items-center gap-2 px-6 py-2">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>$</span>
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAsk()}
          placeholder="Ask about decisions, documents, or policies..."
          className="flex-1 bg-transparent text-xs py-1 outline-none"
          style={{ color: "var(--color-text)" }}
        />
        <button
          onClick={handleAsk}
          disabled={loading || !question.trim()}
          className="px-3 py-1 text-[10px] uppercase tracking-widest border transition-colors"
          style={{
            borderColor: loading || !question.trim() ? "var(--color-border)" : "var(--color-text-muted)",
            color: loading || !question.trim() ? "var(--color-text-muted)" : "var(--color-text)",
            background: "transparent",
          }}
        >
          Ask
        </button>
      </div>
    </div>
  );
}
