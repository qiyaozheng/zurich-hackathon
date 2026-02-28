"use client";

import { useEffect, useRef } from "react";

interface BinData {
  id: string;
  count: number;
  color: string;
}

interface FactoryFloorProps {
  bins: BinData[];
  totalInspected: number;
  passRate: number;
  avgConfidence: number;
  lastAnimation?: { target?: string; part_color?: string } | null;
}

const BIN_POSITIONS: Record<string, { x: number; y: number }> = {
  BIN_A: { x: 0.75, y: 0.15 },
  BIN_B: { x: 0.75, y: 0.35 },
  BIN_C: { x: 0.75, y: 0.55 },
  REJECT_BIN: { x: 0.75, y: 0.78 },
  REVIEW_BIN: { x: 0.90, y: 0.46 },
};

const CAMERA_POS = { x: 0.12, y: 0.46 };
const INSPECT_POS = { x: 0.42, y: 0.46 };

export default function FactoryFloor({
  bins,
  totalInspected,
  passRate,
  avgConfidence,
  lastAnimation,
}: FactoryFloorProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const particlesRef = useRef<
    Array<{ x: number; y: number; tx: number; ty: number; color: string; progress: number }>
  >([]);

  useEffect(() => {
    if (lastAnimation?.target) {
      const binPos = BIN_POSITIONS[lastAnimation.target] || BIN_POSITIONS.REVIEW_BIN;
      particlesRef.current.push({
        x: INSPECT_POS.x,
        y: INSPECT_POS.y,
        tx: binPos.x,
        ty: binPos.y,
        color: lastAnimation.part_color || "#FAFAFA",
        progress: 0,
      });
    }
  }, [lastAnimation]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;

    const draw = () => {
      const w = canvas.width;
      const h = canvas.height;

      ctx.fillStyle = "#0A0A0A";
      ctx.fillRect(0, 0, w, h);

      ctx.strokeStyle = "#1A1A1A";
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 6]);

      ctx.beginPath();
      ctx.moveTo(CAMERA_POS.x * w, CAMERA_POS.y * h);
      ctx.lineTo(INSPECT_POS.x * w, INSPECT_POS.y * h);
      ctx.stroke();

      for (const [, pos] of Object.entries(BIN_POSITIONS)) {
        ctx.beginPath();
        ctx.moveTo(INSPECT_POS.x * w, INSPECT_POS.y * h);
        ctx.lineTo(pos.x * w, pos.y * h);
        ctx.stroke();
      }
      ctx.setLineDash([]);

      ctx.font = "9px 'JetBrains Mono', monospace";
      ctx.textAlign = "center";

      drawNode(ctx, CAMERA_POS.x * w, CAMERA_POS.y * h, "CAM", "#666666", 28);
      drawNode(ctx, INSPECT_POS.x * w, INSPECT_POS.y * h, "INSPECT", "#666666", 36);

      for (const binData of bins) {
        const pos = BIN_POSITIONS[binData.id];
        if (!pos) continue;
        const bx = pos.x * w;
        const by = pos.y * h;
        const isReject = binData.id === "REJECT_BIN";
        const borderColor = isReject ? "#FF3333" : "#2A2A2A";

        ctx.strokeStyle = borderColor;
        ctx.lineWidth = isReject ? 2 : 1;
        ctx.strokeRect(bx - 30, by - 18, 60, 36);

        ctx.fillStyle = isReject ? "#FF3333" : "#FAFAFA";
        ctx.font = "bold 10px 'JetBrains Mono', monospace";
        ctx.fillText(binData.id.replace("_BIN", "").replace("REJECT", "REJ"), bx, by - 2);

        ctx.font = "9px 'JetBrains Mono', monospace";
        ctx.fillStyle = "#666666";
        ctx.fillText(binData.count.toString(), bx, by + 12);
      }

      const alive: typeof particlesRef.current = [];
      for (const p of particlesRef.current) {
        p.progress += 0.015;
        if (p.progress >= 1) continue;
        alive.push(p);

        const t = p.progress;
        const ease = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
        const cx = p.x + (p.tx - p.x) * ease;
        const cy = p.y + (p.ty - p.y) * ease;

        ctx.beginPath();
        ctx.arc(cx * w, cy * h, 6, 0, Math.PI * 2);
        ctx.fillStyle = p.color;
        ctx.fill();

        ctx.beginPath();
        ctx.arc(cx * w, cy * h, 10, 0, Math.PI * 2);
        ctx.strokeStyle = p.color;
        ctx.globalAlpha = 1 - t;
        ctx.lineWidth = 1;
        ctx.stroke();
        ctx.globalAlpha = 1;
      }
      particlesRef.current = alive;

      animId = requestAnimationFrame(draw);
    };

    const resize = () => {
      canvas.width = canvas.offsetWidth * (window.devicePixelRatio || 1);
      canvas.height = canvas.offsetHeight * (window.devicePixelRatio || 1);
      ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);
    };
    resize();
    window.addEventListener("resize", resize);
    draw();

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", resize);
    };
  }, [bins]);

  return (
    <div className="flex flex-col h-full">
      <div className="text-[10px] uppercase tracking-widest mb-2" style={{ color: "var(--color-text-muted)" }}>
        Factory Floor
      </div>
      <div className="border flex-1 min-h-[200px]" style={{ borderColor: "var(--color-border)" }}>
        <canvas ref={canvasRef} className="w-full h-full" />
      </div>
      <div className="grid grid-cols-3 gap-4 mt-3">
        <Metric label="Inspected" value={totalInspected.toString()} />
        <Metric label="Pass Rate" value={totalInspected > 0 ? `${(passRate * 100).toFixed(0)}%` : "—"} />
        <Metric label="Avg Conf" value={totalInspected > 0 ? `${(avgConfidence * 100).toFixed(0)}%` : "—"} />
      </div>
    </div>
  );
}

function drawNode(ctx: CanvasRenderingContext2D, x: number, y: number, label: string, color: string, halfW: number) {
  ctx.strokeStyle = color;
  ctx.lineWidth = 1;
  ctx.strokeRect(x - halfW, y - 14, halfW * 2, 28);
  ctx.fillStyle = "#FAFAFA";
  ctx.font = "bold 9px 'JetBrains Mono', monospace";
  ctx.fillText(label, x, y + 3);
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="text-center">
      <div className="text-2xl font-bold tabular-nums">{value}</div>
      <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--color-text-muted)" }}>
        {label}
      </div>
    </div>
  );
}
