import { useEffect, useState } from "react";
import type { Brief, Snapshot } from "../types";
import { Badge, Card } from "./Common";
import RagGraph from "./RagGraph";

function BriefView({ title, b, tone }: { title: string; b: Brief; tone: string }) {
  return (
    <div className={`rounded-lg border p-3 ${tone}`}>
      <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-300">{title}</div>
      <div className="space-y-1 text-[12px]">
        {Object.values(b.resources).map((r) => (
          <div key={r.name} className="flex justify-between gap-2"><span className="text-slate-400">{r.name}</span>
            <span className="font-mono text-slate-100">{Object.keys(r.owners).join(", ") || "free"}</span></div>
        ))}
        <div className="mt-2 border-t border-navy-600/50 pt-2">
          {Object.entries(b.tasks).map(([id, t]) => (
            <div key={id} className="flex items-center justify-between gap-2 py-0.5">
              <span className="font-mono text-slate-300">{id} ({t.patient})</span><Badge state={t.state as string} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function DeadlockPanel({ snap, act }: { snap: Snapshot; act: (p: string, b?: unknown) => Promise<boolean> }) {
  const det = snap.detection;
  const [victim, setVictim] = useState("");
  const [mode, setMode] = useState<"rollback" | "terminate">("rollback");
  useEffect(() => { setVictim(det?.deadlock ? det.tasks[0] : ""); }, [det?.at, det?.deadlock]); // eslint-disable-line react-hooks/exhaustive-deps
  const rec = snap.recovery;
  const dead = !!det?.deadlock;
  const phase = snap.scenario === "quiescing" ? "Draining in-flight tasks, then the two scenario tasks start..." : null;
  return (
    <Card title="Deadlock demonstration" tone={dead ? "ring-2 ring-rose-500/60" : ""}
      right={dead ? <span className="pulse-red rounded-full bg-rose-500/20 px-2 py-0.5 text-[11px] font-semibold text-rose-300 ring-1 ring-rose-400/50">DEADLOCK DETECTED</span>
        : rec ? <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[11px] font-semibold text-emerald-300 ring-1 ring-emerald-400/40">RECOVERED</span> : undefined}>
      {snap.dispatch_hold && <div className="mb-3 rounded-md bg-amber-400/10 px-3 py-1.5 text-[12px] text-amber-300 ring-1 ring-amber-400/30">Patient dispatch is held while the deadlock scenario runs ({snap.sync.deferred} queued task(s) deferred). {phase}</div>}
      <RagGraph snap={snap} />

      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <div className={`rounded-lg border p-3 ${dead ? "border-rose-500/50 bg-rose-500/10" : "border-navy-600/60 bg-navy-900/60"}`}>
          <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-300">Detection result (wait-for graph)</div>
          {!det && <p className="text-[12.5px] text-slate-400">Detector has not run since the last allocation change. Press <b>Detect deadlock</b>.</p>}
          {det && (
            <div className="space-y-1.5 text-[12.5px]">
              <div className={dead ? "font-semibold text-rose-300" : "font-semibold text-emerald-300"}>{dead ? "Deadlock exists" : "No deadlock"} <span className="font-normal text-slate-500">at {det.at}</span></div>
              {dead && <div className="text-slate-300">Tasks: <span className="font-mono">{det.tasks.join(", ")}</span><br />Cycle: <span className="font-mono">{det.cycle.map((c) => `${c.task} -[${c.resource}]-> ${c.held_by}`).join("  ,  ")}</span></div>}
              <p className="text-slate-300">{det.explanation}</p>
            </div>
          )}
        </div>
        <div className="rounded-lg border border-navy-600/60 bg-navy-900/60 p-3">
          <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-300">Recover deadlock</div>
          <div className="space-y-2 text-[12.5px]">
            <label className="flex items-center justify-between gap-2 text-slate-400">Victim task
              <select value={victim} disabled={!dead} onChange={(e) => setVictim(e.target.value)} className="rounded border border-navy-600 bg-navy-900 px-2 py-1 font-mono text-slate-100 disabled:opacity-40">
                {(det?.tasks ?? []).map((t) => <option key={t}>{t}</option>)}{!dead && <option>-</option>}
              </select></label>
            <label className="flex items-center justify-between gap-2 text-slate-400">Method
              <select value={mode} disabled={!dead} onChange={(e) => setMode(e.target.value as "rollback" | "terminate")} className="rounded border border-navy-600 bg-navy-900 px-2 py-1 text-slate-100 disabled:opacity-40">
                <option value="rollback">Rollback (release and retry later)</option><option value="terminate">Terminate (abort the task)</option>
              </select></label>
            <button disabled={!snap.controls.recover.enabled || !victim} title={snap.controls.recover.enabled ? "" : snap.controls.recover.reason} onClick={() => act("recover", { task_id: victim, mode })}
              className="w-full rounded-md bg-emerald-500 px-3 py-1.5 font-semibold text-navy-950 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-35">Recover deadlock</button>
            {!snap.controls.recover.enabled && <p className="text-[11px] text-slate-500">{snap.controls.recover.reason}</p>}
          </div>
        </div>
      </div>

      {rec && (
        <div className="mt-4">
          <div className="mb-2 rounded-md bg-emerald-500/10 px-3 py-2 text-[12.5px] text-emerald-300 ring-1 ring-emerald-400/30">{rec.message}</div>
          <div className="grid gap-3 md:grid-cols-2">
            <BriefView title="Before recovery" b={rec.before} tone="border-rose-500/40 bg-rose-500/5" />
            <BriefView title="After recovery" b={rec.after} tone="border-emerald-500/40 bg-emerald-500/5" />
          </div>
        </div>
      )}
    </Card>
  );
}
