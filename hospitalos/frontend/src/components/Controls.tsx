import type { Snapshot } from "../types";

type Key = keyof Snapshot["controls"];
const BTN: { key: Key; label: string; path: string; style: string }[] = [
  { key: "start", label: "Start", path: "start", style: "bg-emerald-500 text-navy-950 hover:bg-emerald-400" },
  { key: "pause", label: "Pause", path: "pause", style: "bg-amber-400 text-navy-950 hover:bg-amber-300" },
  { key: "resume", label: "Resume", path: "resume", style: "bg-cyan-500 text-navy-950 hover:bg-cyan-400" },
  { key: "inject", label: "Inject deadlock", path: "inject", style: "bg-rose-500 text-white hover:bg-rose-400" },
  { key: "detect", label: "Detect deadlock", path: "detect", style: "bg-navy-600 text-cyan-200 hover:bg-navy-700 ring-1 ring-cyan-400/40" },
  { key: "reset", label: "Reset", path: "reset", style: "bg-navy-600 text-slate-200 hover:bg-navy-700" },
];

export default function Controls({ snap, act }: { snap: Snapshot; act: (p: string, b?: unknown) => Promise<boolean> }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {BTN.map((b) => {
        const c = snap.controls[b.key];
        return (
          <button key={b.key} disabled={!c.enabled} title={c.enabled ? "" : c.reason} onClick={() => act(b.path)}
            className={`rounded-md px-3.5 py-1.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-35 ${b.style}`}>
            {b.label}
          </button>
        );
      })}
      <span className="text-[11px] text-slate-500">Recover deadlock is in the deadlock panel (choose a victim task).</span>
    </div>
  );
}
