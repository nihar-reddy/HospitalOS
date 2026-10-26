import type { Snapshot } from "../types";
import { Badge, Card, Metric } from "./Common";

export function MetricsRow({ snap }: { snap: Snapshot }) {
  const m = snap.metrics;
  const status = { idle: "Idle", running: "Running", paused: "Paused", completed: "Complete" }[snap.status];
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
      <Metric label="Total patients" value={m.total} />
      <Metric label="Waiting" value={m.waiting} tone="slate" />
      <Metric label="Under treatment" value={m.running} tone="cyan" />
      <Metric label="Completed" value={m.completed} tone="green" />
      <Metric label="Blocked tasks" value={m.blocked} tone={m.blocked ? "amber" : "slate"} hint="Treatment tasks waiting for a hospital resource" />
      <Metric label="Free units" value={m.available_units} tone="green" hint="Unallocated beds + ventilators + procedure rooms" />
      <Metric label="Occupied units" value={m.occupied_units} tone="amber" />
      <Metric label="Status" value={<span className="text-xl">{status}</span>} tone={snap.status === "completed" ? "green" : snap.status === "paused" ? "amber" : "cyan"} />
    </div>
  );
}

export function PatientTable({ snap }: { snap: Snapshot }) {
  const dead = new Set(snap.graph.deadlocked);
  return (
    <Card title="Live patients" right={<span className="text-[11px] text-slate-500">patient / treatment task / thread are separate entities</span>}>
      <div className="max-h-72 overflow-auto">
        <table className="w-full text-left text-[12.5px]">
          <thead className="sticky top-0 bg-navy-800 text-[11px] uppercase text-slate-400">
            <tr><th className="py-1.5 pr-2">Patient</th><th>Urgency</th><th>Task</th><th>Thread</th><th>State</th><th>Holds</th><th>Requests</th><th>Needs</th></tr>
          </thead>
          <tbody>
            {snap.patients.map((p) => (
              <tr key={p.id} className="border-t border-navy-600/40">
                <td className="py-1.5 pr-2 font-mono font-semibold text-slate-100">{p.id}</td>
                <td className={p.urgency === "Critical" ? "text-rose-300" : p.urgency === "Urgent" ? "text-amber-300" : "text-slate-300"}>{p.urgency}</td>
                <td className="font-mono text-slate-400">{p.task}</td>
                <td className="font-mono text-cyan-300">{p.thread ?? "-"}</td>
                <td><Badge state={dead.has(p.task) ? "Deadlocked" : p.state} label={dead.has(p.task) ? "Deadlocked" : p.state} /></td>
                <td className="text-slate-300">{Object.keys(p.held).join(", ") || "-"}</td>
                <td className="text-amber-300">{p.requesting?.resource ?? "-"}</td>
                <td className="text-[11px] text-slate-500">{p.needs.map((n) => n.replace("Emergency ", "").replace("Procedure ", "")).join(" > ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

export function ResourcePanel({ snap }: { snap: Snapshot }) {
  return (
    <Card title="Resource allocation">
      <div className="grid gap-3 md:grid-cols-3">
        {snap.resources.map((r) => (
          <div key={r.key} className="rounded-lg border border-navy-600/60 bg-navy-900/60 p-3">
            <div className="flex items-baseline justify-between">
              <span className="text-sm font-semibold text-slate-100">{r.name}</span>
              <span className="font-mono text-[11px] text-slate-400">{r.allocated}/{r.capacity} used</span>
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5" title={`${r.available} available`}>
              {Array.from({ length: r.capacity }).map((_, i) => (
                <span key={i} className={`h-4 w-7 rounded-sm transition-colors duration-300 ${i < r.allocated ? "bg-amber-400" : "bg-emerald-400/70"}`} />
              ))}
            </div>
            <dl className="mt-2 space-y-0.5 text-[11.5px]">
              <div className="flex justify-between"><dt className="text-slate-400">Available</dt><dd className="font-mono text-emerald-300">{r.available}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-400">Owners</dt><dd className="font-mono text-slate-200">{r.owners.map((o) => `${o.patient}${o.units > 1 ? `x${o.units}` : ""}`).join(", ") || "-"}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-400">Waiting</dt><dd className="font-mono text-amber-300">{r.waiting.map((o) => o.patient).join(", ") || "-"}</dd></div>
            </dl>
          </div>
        ))}
      </div>
    </Card>
  );
}
