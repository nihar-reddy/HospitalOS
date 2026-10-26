export type TaskState = "Waiting" | "Running" | "Blocked" | "Completed" | "Terminated";
export interface Config { patients: number; beds: number; ventilators: number; rooms: number; workers: number }
export interface Patient {
  id: string; urgency: string; state: TaskState; task: string; thread: string | null; needs: string[];
  held: Record<string, number>; attempts: number; registered: boolean; scenario: string | null;
  requesting: { resource: string; units: number } | null;
}
export interface Owner { task: string; patient: string; units: number }
export interface ResourceView {
  key: string; name: string; capacity: number; allocated: number; available: number; owners: Owner[]; waiting: Owner[];
}
export interface ThreadView {
  id: string; name: string; role: string; state: string; task: string | null; patient: string | null;
  activity: string; native_id: number | null; request: { resource: string; holders: string[] } | null;
}
export interface Segment { thread: string; patient: string; task: string; label: string; start: number; end: number | null }
export interface EventView { seq: number; ts: string; t: number; level: string; thread: string | null; msg: string }
export interface GraphTask { id: string; patient: string; state: string; thread: string | null; held: Record<string, number>; requesting: string | null }
export interface Graph {
  resources: { key: string; name: string; capacity: number; allocated: number }[];
  tasks: GraphTask[];
  allocation: { resource: string; task: string; units: number }[];
  requests: { task: string; resource: string; units: number }[];
  deadlocked: string[];
}
export interface CycleStep { task: string; patient: string; waits_for: string; resource: string; held_by: string; holder_patient: string }
export interface Detection { deadlock: boolean; tasks: string[]; cycle: CycleStep[]; explanation: string; at: string }
export interface Brief {
  resources: Record<string, { name: string; capacity: number; owners: Record<string, number>; waiting: string[] }>;
  tasks: Record<string, { patient: string; state: string; held: string[]; requesting: string | null }>;
}
export interface Recovery { victim: string; mode: string; message: string; before: Brief; after: Brief; released: string[]; resumed: string[] }
export interface Control { enabled: boolean; reason: string }
export interface Snapshot {
  version: number; now: number; status: "idle" | "running" | "paused" | "completed";
  config: Config; defaults: Config; limits: Record<keyof Config, [number, number]>;
  controls: Record<"start" | "pause" | "resume" | "inject" | "detect" | "recover" | "reset", Control>;
  scenario: string | null; dispatch_hold: boolean;
  metrics: { total: number; waiting: number; running: number; blocked: number; completed: number; terminated: number; available_units: number; occupied_units: number };
  patients: Patient[]; resources: ResourceView[]; threads: ThreadView[]; graph: Graph; timeline: Segment[]; events: EventView[];
  detection: Detection | null; recovery: Recovery | null;
  sync: { queue_depth: number; urgent_depth: number; in_flight: number; checks: number; violations: number; deferred: number };
}
