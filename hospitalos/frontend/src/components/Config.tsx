import { useEffect, useState } from "react";
import type { Config as Cfg, Snapshot } from "../types";

const FIELDS: { key: keyof Cfg; label: string }[] = [
  { key: "patients", label: "Patients" }, { key: "beds", label: "Emergency beds" }, { key: "ventilators", label: "Ventilators" },
  { key: "rooms", label: "Procedure rooms" }, { key: "workers", label: "Worker threads" },
];

export default function ConfigPanel({ snap, act }: { snap: Snapshot; act: (p: string, b?: unknown) => Promise<boolean> }) {
  const [draft, setDraft] = useState<Cfg>(snap.config);
  useEffect(() => setDraft(snap.config), [JSON.stringify(snap.config)]); // eslint-disable-line react-hooks/exhaustive-deps
  const dirty = JSON.stringify(draft) !== JSON.stringify(snap.config);
  const invalid = FIELDS.some(({ key }) => { const [lo, hi] = snap.limits[key]; const v = draft[key]; return !Number.isInteger(v) || v < lo || v > hi; });
  const running = snap.status === "running" || snap.status === "paused";
  const set = (k: keyof Cfg, raw: string) => setDraft({ ...draft, [k]: raw === "" ? NaN : Number(raw) });
  return (
    <div className="flex flex-wrap items-end gap-3 rounded-xl border border-navy-600/60 bg-navy-800/70 px-4 py-3">
      {FIELDS.map(({ key, label }) => {
        const [lo, hi] = snap.limits[key];
        const bad = !Number.isInteger(draft[key]) || draft[key] < lo || draft[key] > hi;
        return (
          <label key={key} className="flex flex-col text-[11px] text-slate-400" title={`${label}: ${lo} to ${hi} (default ${snap.defaults[key]})`}>
            {label}
            <input type="number" min={lo} max={hi} step={1} value={Number.isNaN(draft[key]) ? "" : draft[key]} onChange={(e) => set(key, e.target.value)}
              className={`mt-1 w-24 rounded-md border bg-navy-900 px-2 py-1 font-mono text-sm text-slate-100 outline-none focus:ring-1 focus:ring-cyan-400 ${bad ? "border-rose-500" : "border-navy-600"}`} />
          </label>
        );
      })}
      <button disabled={invalid || (!dirty && !running && snap.status === "idle")} onClick={() => act("config", draft)}
        title={running ? "Applying stops all worker threads, releases every resource and generates a fresh scenario" : "Apply the configuration and generate a new reproducible scenario"}
        className="rounded-md bg-cyan-500 px-3 py-1.5 text-sm font-semibold text-navy-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-40">
        Apply configuration
      </button>
      <button onClick={() => act("config/defaults")} className="rounded-md border border-navy-600 px-3 py-1.5 text-sm text-slate-300 transition hover:border-cyan-400 hover:text-cyan-300">
        Restore defaults
      </button>
      <span className="ml-auto max-w-xs text-[11px] text-slate-500">Applying safely stops all threads, releases every resource and builds a new reproducible scenario.</span>
    </div>
  );
}
