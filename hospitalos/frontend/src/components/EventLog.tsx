import type { EventView } from "../types";
import { Card, levelStyle } from "./Common";

export default function EventLog({ events, onlyThreads = false, title = "Simulation event log" }: { events: EventView[]; onlyThreads?: boolean; title?: string }) {
  const list = (onlyThreads ? events.filter((e) => e.thread) : events).slice().reverse();
  return (
    <Card title={title} right={<span className="text-[11px] text-slate-500">{list.length} events, newest first</span>}>
      <div className="h-56 overflow-y-auto font-mono text-[12px] leading-5">
        {list.map((e) => (
          <div key={e.seq} className={`flex gap-2 ${levelStyle[e.level] ?? ""}`}>
            <span className="shrink-0 text-slate-500">{e.ts}</span>
            <span className="w-8 shrink-0 text-cyan-500">{e.thread ?? ""}</span>
            <span>{e.msg}</span>
          </div>
        ))}
        {list.length === 0 && <div className="text-slate-500">No events yet.</div>}
      </div>
      <div className="mt-2 flex flex-wrap gap-3 text-[10px] text-slate-500">
        <span className="text-slate-300">normal</span><span className="text-amber-300">waiting</span><span className="text-rose-400">deadlock</span>
        <span className="text-violet-300">recovery</span><span className="text-emerald-300">completion</span>
      </div>
    </Card>
  );
}
