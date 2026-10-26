import type { Snapshot } from "../types";
import { Badge, Card } from "./Common";

export function ThreadMonitor({ snap }: { snap: Snapshot }) {
  const dead = new Set(snap.graph.deadlocked);
  return (
    <Card title="Thread monitor" right={<span className="text-[11px] text-slate-500">Idle = waiting on the queue - Blocked = waiting on a hospital resource - Waiting = barrier or pause</span>}>
      <div className="overflow-auto">
        <table className="w-full text-left text-[12.5px]">
          <thead className="text-[11px] uppercase text-slate-400">
            <tr><th className="py-1.5">ID</th><th>Thread name</th><th>OS tid</th><th>Task</th><th>Patient</th><th>State</th><th>Resource request</th><th>Recent activity</th></tr>
          </thead>
          <tbody>
            {snap.threads.map((t) => {
              const stuck = !!t.task && dead.has(t.task);
              return (
                <tr key={t.id} className="border-t border-navy-600/40 align-top">
                  <td className="py-1.5 font-mono font-semibold text-cyan-300">{t.id}</td>
                  <td className="font-mono text-[11.5px] text-slate-300">{t.name}{t.role === "coordinator" && <span className="ml-1 text-[10px] text-violet-300">coordinator</span>}</td>
                  <td className="font-mono text-[11px] text-slate-500">{t.native_id ?? "-"}</td>
                  <td className="font-mono text-slate-300">{t.task ?? "-"}</td>
                  <td className="font-mono text-slate-100">{t.patient ?? "-"}</td>
                  <td><Badge state={stuck ? "Deadlocked" : t.state} label={stuck ? "Blocked (deadlock)" : t.state} /></td>
                  <td className="text-amber-300">{t.request ? <>{t.request.resource}<span className="text-slate-500"> held by </span><span className="font-mono">{t.request.holders.join(", ") || "-"}</span></> : "-"}</td>
                  <td className="text-slate-400">{t.activity}</td>
                </tr>
              );
            })}
            {snap.threads.length === 0 && <tr><td colSpan={8} className="py-4 text-center text-slate-500">No threads yet. Threads are created when the simulation starts.</td></tr>}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

const segColor = (label: string, dead: boolean) =>
  dead ? "#f43f5e" : label.startsWith("Blocked") ? "#fbbf24" : label === "Treatment" ? "#34d399" : label === "Barrier wait" ? "#a78bfa" : "#22d3ee";

export function Timeline({ snap }: { snap: Snapshot }) {
  const WIN = 40, LEFT = 40, W = 900, ROW = 26;
  const workers = snap.threads.filter((t) => t.role === "worker");
  const end = Math.max(snap.now, WIN), start = end - WIN;
  const x = (t: number) => LEFT + ((Math.max(t, start) - start) / WIN) * (W - LEFT - 10);
  const dead = new Set(snap.graph.deadlocked);
  const H = workers.length * ROW + 34;
  const ticks: number[] = [];
  for (let t = Math.ceil(start / 5) * 5; t <= end; t += 5) ticks.push(t);
  return (
    <Card title="Concurrent execution timeline" right={<span className="text-[11px] text-slate-500">last {WIN}s - real start/end times recorded by worker threads</span>}>
      {workers.length === 0 ? <p className="text-sm text-slate-500">Start the simulation to see worker activity.</p> : (
        <>
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
            {ticks.map((t) => (<g key={t}><line x1={x(t)} x2={x(t)} y1={0} y2={H - 18} stroke="#1d3563" strokeWidth="1" /><text x={x(t)} y={H - 4} fontSize="9" textAnchor="middle" fill="#64748b">{t.toFixed(0)}s</text></g>))}
            {workers.map((w, i) => (
              <g key={w.id}>
                <text x={6} y={i * ROW + 17} fontSize="11" fontWeight="600" fill="#67e8f9" fontFamily="monospace">{w.id}</text>
                <rect x={LEFT} y={i * ROW + 3} width={W - LEFT - 10} height={ROW - 6} fill="#0a1428" rx="3" />
                {snap.timeline.filter((s) => s.thread === w.id && (s.end ?? snap.now) >= start).map((s, k) => {
                  const x1 = x(s.start), x2 = x(s.end ?? snap.now), d = s.label.startsWith("Blocked") && dead.has(s.task);
                  return (
                    <g key={k}>
                      <title>{`${s.thread} - ${s.patient} (${s.task})\n${s.label}\n${s.start.toFixed(2)}s -> ${s.end === null ? "running" : s.end.toFixed(2) + "s"}`}</title>
                      <rect x={x1} y={i * ROW + 4} width={Math.max(2, x2 - x1)} height={ROW - 8} rx="3" fill={segColor(s.label, d)} fillOpacity={0.85} className={d ? "pulse-red" : ""} />
                      {x2 - x1 > 34 && <text x={x1 + 4} y={i * ROW + 16} fontSize="9.5" fontWeight="600" fill="#04101f">{s.patient}</text>}
                    </g>
                  );
                })}
              </g>
            ))}
          </svg>
          <div className="mt-1 flex flex-wrap gap-4 text-[11px] text-slate-400">
            {[["#22d3ee", "Preparation"], ["#34d399", "Treatment"], ["#fbbf24", "Blocked on resource"], ["#a78bfa", "Barrier wait"], ["#f43f5e", "Deadlocked"]].map(([c, l]) => (
              <span key={l}><span className="mr-1 inline-block h-2.5 w-2.5 rounded-sm align-middle" style={{ background: c }} />{l}</span>
            ))}
          </div>
        </>
      )}
    </Card>
  );
}

export function Interaction({ snap }: { snap: Snapshot }) {
  const byTask = new Map(snap.patients.map((p) => [p.task, p]));
  const blocked = snap.threads.filter((t) => t.request && t.task);
  const dead = new Set(snap.graph.deadlocked);
  return (
    <Card title="Thread and deadlock interaction" tone={dead.size ? "ring-2 ring-rose-500/50" : ""}>
      {blocked.length === 0 ? <p className="text-[12.5px] text-slate-400">No thread is blocked on a hospital resource. Inject a deadlock to watch two worker threads block on each other here, and resume after recovery.</p> : (
        <ul className="space-y-1.5 text-[12.5px]">
          {blocked.map((t) => {
            const holders = t.request!.holders.map((h) => `${h}${byTask.get(h)?.thread ? ` on ${byTask.get(h)!.thread}` : ""}`).join(", ");
            return (
              <li key={t.id} className={`rounded-md px-3 py-1.5 ring-1 ${t.task && dead.has(t.task) ? "bg-rose-500/10 text-rose-200 ring-rose-400/40" : "bg-amber-400/10 text-amber-200 ring-amber-400/30"}`}>
                <b className="font-mono">{t.id}</b> ({t.patient}, {t.task}) is blocked requesting <b>{t.request!.resource}</b>, held by <span className="font-mono">{holders || "-"}</span>
                {t.task && dead.has(t.task) ? " - part of the deadlock cycle" : " - ordinary waiting"}
              </li>
            );
          })}
        </ul>
      )}
      {snap.recovery && <p className="mt-2 text-[12.5px] text-emerald-300">Last recovery: {snap.recovery.message}</p>}
    </Card>
  );
}

export function SyncPanel({ snap }: { snap: Snapshot }) {
  const s = snap.sync;
  const rows: [string, string, string][] = [
    ["Condition + RLock", "Mutual exclusion on all resource allocation/release; blocked tasks wait on it without holding it", `${snap.metrics.occupied_units} units allocated`],
    ["queue.Queue (main)", "Admission thread feeds tasks to the worker pool", `${s.queue_depth} queued`],
    ["queue.Queue (urgent)", "Deadlock-demo tasks bypass normal intake", `${s.urgent_depth} queued`],
    ["threading.Barrier", "Both deadlock tasks hold their first resource before requesting the second", snap.scenario === "active" ? "armed" : "idle"],
    ["threading.Event", "Cooperative shutdown and bounded waits (0.05-0.25 s slices)", snap.dispatch_hold ? "dispatch held" : "dispatch open"],
    ["Invariant monitor", "Verifies allocated <= capacity and owner bookkeeping", `${s.checks} checks, ${s.violations} violations`],
  ];
  return (
    <Card title="Synchronization primitives in use">
      <table className="w-full text-[12.5px]"><tbody>
        {rows.map(([a, b, c]) => (
          <tr key={a} className="border-t border-navy-600/40 first:border-0"><td className="py-1.5 pr-3 font-mono text-cyan-300">{a}</td><td className="pr-3 text-slate-400">{b}</td><td className="whitespace-nowrap text-right font-mono text-slate-200">{c}</td></tr>
        ))}
      </tbody></table>
    </Card>
  );
}
