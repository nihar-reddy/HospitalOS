import { useState } from "react";
import type { Snapshot } from "../types";

const W = 760, H = 340;
type P = { x: number; y: number };

function edgePoint(c: P, other: P, shape: { r?: number; hw?: number; hh?: number }): P {
  const dx = other.x - c.x, dy = other.y - c.y, len = Math.hypot(dx, dy) || 1;
  if (shape.r) return { x: c.x + (dx / len) * (shape.r + 2), y: c.y + (dy / len) * (shape.r + 2) };
  const s = Math.min((shape.hw ?? 1) / (Math.abs(dx) || 1e-6), (shape.hh ?? 1) / (Math.abs(dy) || 1e-6));
  return { x: c.x + dx * s, y: c.y + dy * s };
}

export default function RagGraph({ snap }: { snap: Snapshot }) {
  const [sel, setSel] = useState<string | null>(null);
  const g = snap.graph;
  const dead = new Set(g.deadlocked);
  const cyc = snap.detection?.deadlock ? snap.detection.cycle : [];
  const redReq = new Set(cyc.map((c) => `${c.task}>${c.waits_for}`));
  const redAlloc = new Set(cyc.map((c) => `${c.waits_for}>${c.held_by}`));

  const rpos: Record<string, P> = {};
  g.resources.forEach((r, i) => (rpos[r.key] = { x: ((i + 1) * W) / (g.resources.length + 1), y: H / 2 }));
  const tpos: Record<string, P> = {};
  const rows: string[][] = [[], []];
  g.tasks.slice(0, 14).forEach((t, i) => rows[i % 2].push(t.id));
  rows.forEach((ids, row) => ids.forEach((id, j) => (tpos[id] = { x: ((j + 1) * W) / (ids.length + 1), y: row === 0 ? 48 : H - 48 })));

  const RW = 64, RH = 24, TR = 28;
  const details = (() => {
    if (!sel) return null;
    const r = snap.resources.find((x) => x.key === sel);
    if (r) return (
      <>
        <b className="text-cyan-300">{r.name}</b>: capacity {r.capacity}, allocated {r.allocated}, available {r.available}. Owners: {r.owners.map((o) => `${o.task} (${o.patient}, ${o.units})`).join(", ") || "none"}. Waiting: {r.waiting.map((o) => o.task).join(", ") || "none"}.
      </>
    );
    const t = snap.patients.find((x) => x.task === sel);
    if (t) return (
      <>
        <b className="text-cyan-300">{t.task}</b> for patient {t.id} ({t.urgency}) - state <b>{dead.has(t.task) ? "Deadlocked" : t.state}</b>, thread {t.thread ?? "none"}. Holds: {Object.entries(t.held).map(([k, v]) => `${k} x${v}`).join(", ") || "nothing"}. Requests: {t.requesting?.resource ?? "nothing"}.
      </>
    );
    return null;
  })();

  const arrow = (id: string, color: string) => (
    <marker id={id} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill={color} /></marker>
  );

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full rounded-lg bg-navy-950/70 ring-1 ring-navy-600/60" role="img" aria-label="Resource allocation graph">
        <defs>{arrow("a-cyan", "#22d3ee")}{arrow("a-amber", "#fbbf24")}{arrow("a-red", "#f43f5e")}</defs>
        {g.allocation.map((a) => {
          const rp = rpos[a.resource], tp = tpos[a.task];
          if (!rp || !tp) return null;
          const s = edgePoint(rp, tp, { hw: RW, hh: RH }), e = edgePoint(tp, rp, { r: TR });
          const red = redAlloc.has(`${a.resource}>${a.task}`);
          return (
            <g key={`al-${a.resource}-${a.task}`} className="transition-all">
              <line x1={s.x} y1={s.y} x2={e.x} y2={e.y} stroke={red ? "#f43f5e" : "#22d3ee"} strokeWidth={red ? 3 : 2} markerEnd={`url(#${red ? "a-red" : "a-cyan"})`} />
              <text x={(s.x + e.x) / 2 + 6} y={(s.y + e.y) / 2} fontSize="10" fill="#67e8f9">holds{a.units > 1 ? ` x${a.units}` : ""}</text>
            </g>
          );
        })}
        {g.requests.map((q) => {
          const rp = rpos[q.resource], tp = tpos[q.task];
          if (!rp || !tp) return null;
          const s = edgePoint(tp, rp, { r: TR }), e = edgePoint(rp, tp, { hw: RW, hh: RH });
          const red = redReq.has(`${q.task}>${q.resource}`);
          return (
            <g key={`rq-${q.task}-${q.resource}`}>
              <line x1={s.x} y1={s.y} x2={e.x} y2={e.y} stroke={red ? "#f43f5e" : "#fbbf24"} strokeWidth={red ? 3 : 2} strokeDasharray="6 4" markerEnd={`url(#${red ? "a-red" : "a-amber"})`} />
              <text x={(s.x + e.x) / 2 + 6} y={(s.y + e.y) / 2 - 4} fontSize="10" fill="#fcd34d">requests</text>
            </g>
          );
        })}
        {g.resources.map((r) => {
          const p = rpos[r.key], full = r.allocated >= r.capacity;
          const inCycle = cyc.some((c) => c.waits_for === r.key);
          return (
            <g key={r.key} onClick={() => setSel(r.key)} className="cursor-pointer">
              <title>{`${r.name}: ${r.allocated}/${r.capacity} allocated`}</title>
              <rect x={p.x - RW} y={p.y - RH} width={RW * 2} height={RH * 2} rx="8" fill="#0d1b3a" stroke={inCycle ? "#f43f5e" : sel === r.key ? "#22d3ee" : full ? "#fbbf24" : "#34d399"} strokeWidth={sel === r.key || inCycle ? 3 : 2} />
              <text x={p.x} y={p.y - 3} textAnchor="middle" fontSize="12" fontWeight="600" fill="#e2e8f0">{r.name}</text>
              <text x={p.x} y={p.y + 13} textAnchor="middle" fontSize="10" fill="#94a3b8">{r.allocated}/{r.capacity} used</text>
            </g>
          );
        })}
        {g.tasks.filter((t) => tpos[t.id]).map((t) => {
          const p = tpos[t.id], d = dead.has(t.id);
          const color = d ? "#f43f5e" : t.state === "Blocked" ? "#fbbf24" : "#22d3ee";
          return (
            <g key={t.id} onClick={() => setSel(t.id)} className="cursor-pointer">
              <title>{`${t.id} (${t.patient}) - ${d ? "Deadlocked" : t.state}`}</title>
              <circle cx={p.x} cy={p.y} r={TR} fill="#0a1428" stroke={color} strokeWidth={sel === t.id || d ? 3.5 : 2} className={d ? "pulse-red" : ""} />
              <text x={p.x} y={p.y - 2} textAnchor="middle" fontSize="12" fontWeight="700" fill={color}>{t.patient}</text>
              <text x={p.x} y={p.y + 11} textAnchor="middle" fontSize="8.5" fill="#94a3b8">{t.id}</text>
            </g>
          );
        })}
        {g.tasks.length === 0 && <text x={W / 2} y={H / 2 + 70} textAnchor="middle" fontSize="12" fill="#64748b">No task currently holds or requests a resource. Start the simulation or inject a deadlock.</text>}
      </svg>
      <div className="mt-2 flex flex-wrap items-center gap-4 text-[11px] text-slate-400">
        <span><span className="mr-1 inline-block h-0.5 w-5 bg-cyan-400 align-middle" />allocation (resource to task)</span>
        <span><span className="mr-1 inline-block h-0.5 w-5 border-t-2 border-dashed border-amber-400 align-middle" />request (task to resource)</span>
        <span><span className="mr-1 inline-block h-0.5 w-5 bg-rose-500 align-middle" />circular wait</span>
        <span className="text-slate-500">Click a node for details.</span>
      </div>
      {details && <div className="mt-2 rounded-md bg-navy-900/70 px-3 py-2 text-[12px] text-slate-300 ring-1 ring-navy-600/60">{details}</div>}
    </div>
  );
}
