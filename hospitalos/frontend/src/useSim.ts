import { useCallback, useEffect, useState } from "react";
import type { Snapshot } from "./types";

export interface Toast { kind: "error" | "ok"; text: string }

export function useSim() {
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [live, setLive] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let timer: number | undefined;
    let closed = false;
    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${location.host}/ws`);
      ws.onopen = () => setLive(true);
      ws.onmessage = (e) => setSnap(JSON.parse(e.data) as Snapshot);
      ws.onclose = () => {
        setLive(false);
        if (!closed) timer = window.setTimeout(connect, 1000);
      };
      ws.onerror = () => ws?.close();
    };
    connect();
    return () => { closed = true; window.clearTimeout(timer); ws?.close(); };
  }, []);

  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), toast.kind === "error" ? 6000 : 4000);
    return () => window.clearTimeout(t);
  }, [toast]);

  const act = useCallback(async (path: string, body?: unknown): Promise<boolean> => {
    try {
      const res = await fetch(`/api/${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body ?? {}) });
      const data = await res.json();
      if (!res.ok) {
        setToast({ kind: "error", text: typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail) });
        return false;
      }
      if (data.state) setSnap(data.state as Snapshot);
      if (data.message) setToast({ kind: "ok", text: data.message as string });
      return true;
    } catch {
      setToast({ kind: "error", text: "Backend unreachable. Is it running on port 8000?" });
      return false;
    }
  }, []);

  return { snap, live, act, toast, clearToast: () => setToast(null) };
}
