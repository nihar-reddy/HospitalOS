import type { ReactNode } from "react";

export const stateStyle: Record<string, string> = {
  Waiting: "bg-slate-500/15 text-slate-300 ring-slate-400/30",
  Running: "bg-cyan-400/15 text-cyan-300 ring-cyan-400/40",
  Blocked: "bg-amber-400/15 text-amber-300 ring-amber-400/40",
  Completed: "bg-emerald-400/15 text-emerald-300 ring-emerald-400/40",
  Terminated: "bg-rose-500/15 text-rose-300 ring-rose-400/40",
  Idle: "bg-slate-500/15 text-slate-300 ring-slate-400/30",
  Stopping: "bg-slate-500/15 text-slate-400 ring-slate-400/30",
  Stopped: "bg-slate-600/15 text-slate-500 ring-slate-500/30",
  Deadlocked: "bg-rose-500/20 text-rose-300 ring-rose-400/60",
};

export function Badge({ state, label }: { state: string; label?: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${stateStyle[state] ?? stateStyle.Idle}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" />{label ?? state}
    </span>
  );
}

export function Card({ title, right, children, className = "", tone = "" }: { title?: ReactNode; right?: ReactNode; children: ReactNode; className?: string; tone?: string }) {
  return (
    <section className={`rounded-xl border border-navy-600/60 bg-navy-800/70 shadow-lg shadow-black/20 backdrop-blur ${tone} ${className}`}>
      {title !== undefined && (
        <header className="flex items-center justify-between gap-3 border-b border-navy-600/50 px-4 py-2.5">
          <h2 className="text-[13px] font-semibold uppercase tracking-wider text-cyan-300">{title}</h2>
          {right}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

const toneText: Record<string, string> = { cyan: "text-cyan-300", amber: "text-amber-300", green: "text-emerald-300", red: "text-rose-300", slate: "text-slate-100" };
export function Metric({ label, value, tone = "slate", hint }: { label: string; value: ReactNode; tone?: string; hint?: string }) {
  return (
    <div title={hint} className="rounded-lg border border-navy-600/60 bg-navy-800/70 px-3 py-2.5">
      <div className="text-[11px] uppercase tracking-wide text-slate-400">{label}</div>
      <div className={`mt-0.5 font-mono text-2xl font-semibold transition-all ${toneText[tone]}`}>{value}</div>
    </div>
  );
}

export const levelStyle: Record<string, string> = {
  info: "text-slate-300", wait: "text-amber-300", deadlock: "text-rose-400", recovery: "text-violet-300",
  success: "text-emerald-300", error: "text-rose-500",
};
