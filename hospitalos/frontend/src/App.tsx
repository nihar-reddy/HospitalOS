import { useState } from "react";
import ConfigPanel from "./components/Config";
import Controls from "./components/Controls";
import DeadlockPanel from "./components/DeadlockPanel";
import { MetricsRow, PatientTable, ResourcePanel } from "./components/Emergency";
import EventLog from "./components/EventLog";
import { Interaction, SyncPanel, ThreadMonitor, Timeline } from "./components/Threads";
import { useSim } from "./useSim";

const TABS = ["Emergency & Deadlock", "Multithreading"] as const;

export default function App() {
  const { snap, live, act, toast, clearToast } = useSim();
  const [tab, setTab] = useState<(typeof TABS)[number]>(TABS[0]);

  if (!snap) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-2 text-slate-400">
        <div className="text-2xl font-semibold text-cyan-300">HospitalOS</div>
        <div>{live ? "Loading state..." : "Connecting to the backend on port 8000..."}</div>
      </div>
    );
  }
  const deadlocked = snap.graph.deadlocked.length > 0;
  return (
    <div className="mx-auto max-w-[1500px] space-y-4 px-4 py-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-lg bg-cyan-500/15 text-lg font-bold text-cyan-300 ring-1 ring-cyan-400/40">+</div>
          <div>
            <h1 className="text-lg font-semibold leading-tight text-slate-100">HospitalOS <span className="font-normal text-slate-400">- Emergency Resource Coordination Simulator</span></h1>
            <p className="text-[11px] text-slate-500">Educational simulation of multithreading and deadlock management. Not a clinical system.</p>
          </div>
        </div>
        <div className="flex items-center gap-2 text-[11px]">
          {deadlocked && <span className="pulse-red rounded-full bg-rose-500/20 px-2.5 py-1 font-semibold text-rose-300 ring-1 ring-rose-400/50">DEADLOCK</span>}
          <span className={`rounded-full px-2.5 py-1 ring-1 ${live ? "bg-emerald-500/10 text-emerald-300 ring-emerald-400/30" : "bg-rose-500/10 text-rose-300 ring-rose-400/30"}`}>{live ? "Live (WebSocket)" : "Reconnecting..."}</span>
        </div>
      </header>

      <ConfigPanel snap={snap} act={act} />
      <div className="sticky top-0 z-10 -mx-4 border-y border-navy-600/50 bg-navy-950/90 px-4 py-2.5 backdrop-blur"><Controls snap={snap} act={act} /></div>

      {toast && (
        <div onClick={clearToast} className={`cursor-pointer rounded-md px-3 py-2 text-[13px] ring-1 ${toast.kind === "error" ? "bg-rose-500/10 text-rose-200 ring-rose-400/40" : "bg-cyan-500/10 text-cyan-100 ring-cyan-400/30"}`}>{toast.text}</div>
      )}

      <nav className="flex gap-1 border-b border-navy-600/60">
        {TABS.map((t) => (
          <button key={t} onClick={() => setTab(t)} className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium transition ${tab === t ? "border-cyan-400 text-cyan-300" : "border-transparent text-slate-400 hover:text-slate-200"}`}>{t}</button>
        ))}
      </nav>

      {tab === TABS[0] ? (
        <div className="space-y-4">
          <MetricsRow snap={snap} />
          <div className="grid gap-4 xl:grid-cols-5">
            <div className="space-y-4 xl:col-span-2"><PatientTable snap={snap} /><ResourcePanel snap={snap} /></div>
            <div className="xl:col-span-3"><DeadlockPanel snap={snap} act={act} /></div>
          </div>
          <EventLog events={snap.events} />
        </div>
      ) : (
        <div className="space-y-4">
          <MetricsRow snap={snap} />
          <ThreadMonitor snap={snap} />
          <Timeline snap={snap} />
          <div className="grid gap-4 xl:grid-cols-2"><Interaction snap={snap} /><SyncPanel snap={snap} /></div>
          <EventLog events={snap.events} onlyThreads title="Thread events" />
        </div>
      )}
    </div>
  );
}
