# HospitalOS - Emergency Resource Coordination Simulator

An educational Operating Systems project showing **multithreading + synchronization** and **deadlock management** on one shared emergency-department simulation. Python backend (real `threading`), FastAPI + WebSockets, React + TypeScript + Tailwind frontend. Not a clinical system.

## Project layout
```
backend/engine.py          simulation: worker threads, resource manager, deadlock scenario, detection, recovery
backend/main.py            FastAPI REST controls + /ws live state
backend/tests/             unittest/pytest tests (engine + API)
frontend/src/              React UI (two tabs: "Emergency & Deadlock", "Multithreading")
```

## Install (macOS)
```bash
brew install python node            # skip if already installed (Python 3.9+, Node 18+)
cd hospitalos/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd ../frontend
npm install
```

## Run (two terminals)
```bash
# Terminal 1 - backend  -> http://127.0.0.1:8000  (API docs at /docs)
cd hospitalos/backend && source .venv/bin/activate
uvicorn main:app --port 8000

# Terminal 2 - frontend -> http://localhost:5173
cd hospitalos/frontend
npm run dev
```
Open **http://localhost:5173**. (Vite proxies `/api` and `/ws` to port 8000.)

## Tests
```bash
cd hospitalos/backend && source .venv/bin/activate
python -m pytest -v            # or: python -m unittest discover -s tests -v
```
Covers: config validation, reproducible scenarios, capacity enforcement under 12-thread contention, owner-only release, real overlapping worker execution, no false deadlock during normal waiting, deterministic deadlock, detection, rollback and terminate recovery, pause/resume, safe reset/repeat, responsiveness while deadlocked, and the REST/WebSocket flow.

## Demo script (2 minutes)
1. Leave defaults (6 patients, 2 beds, 1 ventilator, 1 room, 4 workers) and press **Start**. Watch patients move Waiting -> Running and resources fill. Open **Multithreading**: T1-T4 process different patients with overlapping timeline bars.
2. Press **Reset**, then **Inject deadlock** (or inject while running). Intake is held, the in-flight work drains, then TASK-001/P001 takes the ventilator and TASK-002/P002 takes the procedure room (barrier makes this deterministic), and each then requests the other's resource.
3. Press **Detect deadlock**: the graph shows the red cycle, the panel names tasks, resources and why neither can proceed. In the Multithreading tab two threads show **Blocked**, each naming the resource and the holder.
4. Choose a victim, press **Recover deadlock**. Resources are released, the other task resumes, and the before/after panel shows the change. The rolled-back task re-queues and finishes later. **Reset** and repeat.

## How it maps to the spec
* **Five parameters only**, validated (patients 2-20, beds 1-8, ventilators 1-4, rooms 1-4, workers 2-8). Applying always stops all threads cleanly and rebuilds, so allocations can never be corrupted. The scenario is seeded from the configuration, so it is reproducible. Treatment durations and intervals are internal constants.
* **Real threads**: `Worker-1..N` (count = *Worker threads*), plus an *Admission* thread (registers patients and fills the queue) and a *Monitor* thread (verifies resource invariants). Shown in the thread table with real OS thread ids.
* **Deadlock scenario**: the two scenario tasks each take *all units* of their first resource (so it is exclusive for any capacity), wait on a `threading.Barrier`, then request the other's. Normal patients acquire in a fixed order (bed, ventilator, room), so ordinary load can wait but never deadlock.
* **Detection**: a reduction (multi-instance safe) finds truly deadlocked tasks; a wait-for graph DFS extracts the cycle. Ordinary waiting is reported as "no deadlock".
* **Recovery**: rollback (release + re-queue) or terminate. Resources are released in the backend, waiters are notified, the other thread resumes; the dashboard shows real before/after state.
* **Responsiveness**: the state lock is never held while waiting; blocked tasks use `Condition.wait(0.25)`, sleeps are 50 ms slices, and shutdown is cooperative via an `Event`.

## Troubleshooting
* *Page says "Connecting to the backend"*: start the backend first on port 8000; check `curl http://127.0.0.1:8000/api/state`.
* *Port in use*: `lsof -i :8000` (or `:5173`), then `kill <pid>`; or use `uvicorn main:app --port 8001` and change the proxy targets in `frontend/vite.config.ts`.
* *`ModuleNotFoundError`*: activate the venv (`source .venv/bin/activate`) and rerun `pip install -r requirements.txt`.
* *`npm install` fails*: use Node 18+ (`node -v`), delete `node_modules`, retry.
* *Inject deadlock disabled*: hover the button for the reason (needs two patients not yet treated; press Reset).

## Viva notes
* **Multithreading**: several threads of one process run concurrently and share memory. Here each worker repeatedly takes a treatment task from a `queue.Queue` and runs it, so different patients are treated at the same time (see overlapping timeline bars with real timestamps).
* **Synchronization**: shared state (resource tables, task states) is protected by one `Condition` over an `RLock`, giving mutual exclusion; allocation is atomic so capacity is never exceeded. `Queue` is a thread-safe producer/consumer channel, `Barrier` aligns the deadlock tasks, `Event` stops threads cooperatively.
* **Deadlock** needs four conditions: mutual exclusion (units are exclusive), hold-and-wait (a task keeps one resource while requesting another), no preemption (resources are not taken away), circular wait (P001 waits for P002 which waits for P001).
* **Prevention vs detection**: normal workload prevents circular wait with resource ordering; the demo deliberately breaks that order, then **detects** the cycle with a wait-for graph (edge A->B: A waits for a resource B holds; a cycle means deadlock).
* **Recovery**: pick a victim, roll it back (release its resources and retry later) or terminate it; the waiting task becomes eligible, is granted the resource, and the cycle disappears.
