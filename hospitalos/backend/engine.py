"""HospitalOS simulation engine.

Pure Python (no web framework). Everything the dashboard shows comes from here:
real worker threads, a lock/condition protected resource manager, a deterministic
deadlock scenario, wait-for-graph detection and rollback/terminate recovery.

Concurrency design
------------------
* ``self.cond`` (a Condition over an RLock) is the single "state lock". It guards every
  shared structure: resources, tasks, events, timeline, thread table.
* The state lock is only ever held for short critical sections. Blocking on a hospital
  resource uses ``cond.wait(0.25)`` which RELEASES the lock, so a deadlocked treatment
  task never freezes the API, the WebSocket, detection or recovery.
* Workers pull tasks from ``queue.Queue`` objects. Sleeping (treatment) happens outside
  the lock in small, stop/pause-aware slices.
"""
from __future__ import annotations

import queue
import random
import threading
import time
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

RES_ORDER = ["bed", "ventilator", "room"]  # global acquisition order (prevents accidental deadlock)
RES_NAMES = {"bed": "Emergency Beds", "ventilator": "Ventilators", "room": "Procedure Rooms"}
CAP_KEY = {"bed": "beds", "ventilator": "ventilators", "room": "rooms"}
DEFAULTS = {"patients": 6, "beds": 2, "ventilators": 1, "rooms": 1, "workers": 4}
LIMITS = {"patients": (2, 20), "beds": (1, 8), "ventilators": (1, 4), "rooms": (1, 4), "workers": (2, 8)}

PREP_SECONDS = 0.5
ADMIT_INTERVAL = 0.35
SCENARIO_TREAT = 1.5
BARRIER_TIMEOUT = 20.0


class ConfigError(ValueError):
    pass


class ActionError(RuntimeError):
    pass


class OwnershipError(RuntimeError):
    pass


class Aborted(Exception):
    """Raised inside a treatment task to unwind it (rollback / terminate / shutdown)."""


def validate_config(raw: Dict[str, Any]) -> Dict[str, int]:
    if not isinstance(raw, dict):
        raise ConfigError("Configuration must be an object with five numeric fields.")
    unknown = set(raw) - set(DEFAULTS)
    if unknown:
        raise ConfigError("Unknown configuration field(s): " + ", ".join(sorted(unknown)))
    out: Dict[str, int] = {}
    for key, default in DEFAULTS.items():
        val = raw.get(key, default)
        if isinstance(val, bool) or not isinstance(val, (int, float)) or int(val) != val:
            raise ConfigError(f"{key} must be a whole number.")
        lo, hi = LIMITS[key]
        if not lo <= int(val) <= hi:
            raise ConfigError(f"{key} must be between {lo} and {hi}.")
        out[key] = int(val)
    return out


class Resource:
    def __init__(self, key: str, capacity: int):
        self.key, self.name, self.capacity = key, RES_NAMES[key], capacity
        self.owners: Dict[str, int] = {}          # task id -> units
        self.waiting: List[Tuple[str, int]] = []  # (task id, units)

    @property
    def allocated(self) -> int:
        return sum(self.owners.values())

    @property
    def available(self) -> int:
        return self.capacity - self.allocated


class Patient:
    def __init__(self, pid: str, urgency: str, needs: List[str], duration: float, task_id: str):
        self.id, self.urgency, self.needs, self.duration, self.task_id = pid, urgency, needs, duration, task_id
        self.registered = False


class Task:
    """A treatment task: the process-like entity executed by a worker thread."""

    def __init__(self, tid: str, patient_id: str):
        self.id, self.patient_id = tid, patient_id
        self.state = "Waiting"  # Waiting | Running | Blocked | Completed | Terminated
        self.held: Dict[str, int] = {}
        self.requesting: Optional[Tuple[str, int]] = None
        self.thread: Optional[str] = None
        self.abort: Optional[str] = None  # None | rollback | terminate
        self.scenario: Optional[str] = None  # None | A | B (deadlock demo roles)
        self.ticket = 0  # invalidates stale queue entries
        self.attempts = 0


class ThreadInfo:
    def __init__(self, tid: str, name: str, role: str):
        self.tid, self.name, self.role = tid, name, role
        self.state, self.activity = "Idle", "Started"
        self.task: Optional[str] = None
        self.patient: Optional[str] = None
        self.request: Optional[Dict[str, Any]] = None
        self.native_id: Optional[int] = None
        self.seg: Optional[Dict[str, Any]] = None
        self.seg_label: Optional[str] = None


class Engine:
    def __init__(self, config: Optional[Dict[str, Any]] = None, speed: float = 1.0):
        self.speed = float(speed)  # internal timing scale (tests use <1); not user-configurable
        self.cond = threading.Condition(threading.RLock())
        self._threads: List[threading.Thread] = []
        self._build(validate_config(config or DEFAULTS))

    # ------------------------------------------------------------------ setup
    def _build(self, cfg: Dict[str, int]) -> None:
        self.config = dict(cfg)
        seed = cfg["patients"] * 10007 + cfg["beds"] * 1009 + cfg["ventilators"] * 101 + cfg["rooms"] * 13 + cfg["workers"]
        rng = random.Random(seed)  # reproducible scenario for a given configuration
        self.stop = threading.Event()
        self.paused = False
        self.status = "idle"
        self.version = 0
        self.seq = 0
        self.t0 = time.time()
        self.events: deque = deque(maxlen=300)
        self.timeline: List[Dict[str, Any]] = []
        self.res = {k: Resource(k, cfg[CAP_KEY[k]]) for k in RES_ORDER}
        self.patients: Dict[str, Patient] = {}
        self.tasks: Dict[str, Task] = {}
        for i in range(cfg["patients"]):
            pid, tid = f"P{i + 1:03d}", f"TASK-{i + 1:03d}"
            urgency = rng.choices(["Critical", "Urgent", "Standard"], weights=[2, 3, 3])[0]
            needs = ["bed"]
            if urgency == "Critical" or rng.random() < 0.3:
                needs.append("ventilator")
            if rng.random() < (0.4 if urgency == "Critical" else 0.5):
                needs.append("room")
            self.patients[pid] = Patient(pid, urgency, needs, round(rng.uniform(1.2, 2.6), 2), tid)
            self.tasks[tid] = Task(tid, pid)
        self.main_q: queue.Queue = queue.Queue()
        self.urgent_q: queue.Queue = queue.Queue()
        self.deferred: List[Tuple[int, Task]] = []
        self.hold = False          # dispatch hold while the deadlock demo is prepared / active
        self.scenario: Optional[str] = None  # None | quiescing | active
        self.in_flight = 0
        self.barrier: Optional[threading.Barrier] = None
        self.detection: Optional[Dict[str, Any]] = None
        self.recovery: Optional[Dict[str, Any]] = None
        self.tinfo: Dict[str, ThreadInfo] = {}
        self.violations: List[str] = []
        self.checks = 0
        self._log("info", f"Scenario generated: {cfg['patients']} patients, {cfg['beds']} beds, "
                          f"{cfg['ventilators']} ventilators, {cfg['rooms']} procedure rooms, {cfg['workers']} workers")

    def _log(self, level: str, msg: str, ti: Optional[ThreadInfo] = None) -> None:
        with self.cond:
            self.seq += 1
            now = time.time()
            self.events.append({"seq": self.seq, "level": level, "msg": msg, "thread": ti.tid if ti else None,
                                "ts": time.strftime("%H:%M:%S", time.localtime(now)) + f".{int(now % 1 * 1000):03d}",
                                "t": round(now - self.t0, 3)})
            self.version += 1

    def _touch(self) -> None:
        with self.cond:
            self.version += 1

    # ------------------------------------------------------------ resources
    def _check_abort(self, task: Task) -> None:
        if self.stop.is_set():
            raise Aborted("shutdown")
        if task.abort:
            raise Aborted(task.abort)

    def _grant(self, task: Task, r: Resource, units: int, ti: Optional[ThreadInfo]) -> None:
        with self.cond:
            r.owners[task.id] = r.owners.get(task.id, 0) + units
            task.held[r.key] = task.held.get(r.key, 0) + units
            if r.allocated > r.capacity:  # can never happen; the monitor also verifies it
                self.violations.append(f"{r.name} over-allocated")
            self.detection = None
            self._log("info", f"{r.name} allocated to {task.patient_id} ({task.id}) - {units} unit(s), "
                              f"{r.available}/{r.capacity} now free", ti)

    def _acquire(self, task: Task, rk: str, units: int, ti: ThreadInfo) -> None:
        """Mutual-exclusion allocation. Blocks (without holding the lock) until granted or aborted."""
        with self.cond:
            r = self.res[rk]
            self._check_abort(task)
            if r.available >= units:
                self._grant(task, r, units, ti)
                return
            prev = ti.seg_label
            holders = [o for o in r.owners if o != task.id]
            r.waiting.append((task.id, units))
            task.state, task.requesting = "Blocked", (rk, units)
            ti.state, ti.activity = "Blocked", f"Blocked on {r.name}"
            ti.request = {"resource": r.name, "holders": holders}
            self._log("wait", f"Thread {ti.tid} requested {r.name} for {task.patient_id}; none free - "
                              f"{task.id} blocked (held by {', '.join(holders) or 'nobody'})", ti)
            self._seg(ti, task, f"Blocked: {r.name}")
            try:
                while True:
                    self._check_abort(task)
                    if r.available >= units:
                        break
                    self.cond.wait(0.25)  # releases the state lock while waiting
                    if ti.request is not None:
                        ti.request["holders"] = [o for o in r.owners if o != task.id]
            finally:
                r.waiting = [w for w in r.waiting if w[0] != task.id]
                task.requesting, ti.request = None, None
            task.state, ti.state = "Running", "Running"
            ti.activity = f"Acquired {r.name}"
            self._grant(task, r, units, ti)
            self._seg(ti, task, prev or "Treatment")
            self._log("info", f"Blocked task {task.id} resumed after receiving {r.name}", ti)

    def _release(self, task: Task, rk: str, ti: Optional[ThreadInfo], level: str = "info") -> None:
        with self.cond:
            r = self.res[rk]
            if task.id not in r.owners:
                raise OwnershipError(f"{task.id} does not own {r.name}")
            units = r.owners.pop(task.id)
            task.held.pop(rk, None)
            self.detection = None
            self._log(level, f"{r.name} released by {task.patient_id} ({task.id}) - {units} unit(s), "
                             f"{r.available}/{r.capacity} now free", ti)
            self.cond.notify_all()

    def _release_all(self, task: Task, ti: Optional[ThreadInfo], level: str = "info") -> List[str]:
        released = []
        with self.cond:
            for rk in list(task.held):
                try:
                    units = self.res[rk].owners.get(task.id, 0)
                    self._release(task, rk, ti, level)
                    released.append(f"{self.res[rk].name} x{units}")
                except OwnershipError:
                    task.held.pop(rk, None)
        return released

    # ------------------------------------------------------------ timeline
    def _close_seg(self, ti: ThreadInfo) -> None:
        if ti.seg and ti.seg["end"] is None:
            ti.seg["end"] = round(time.time() - self.t0, 3)
        ti.seg = None

    def _seg(self, ti: ThreadInfo, task: Optional[Task], label: Optional[str]) -> None:
        with self.cond:
            self._close_seg(ti)
            if label is None or task is None:
                return
            seg = {"thread": ti.tid, "patient": task.patient_id, "task": task.id, "label": label,
                   "start": round(time.time() - self.t0, 3), "end": None}
            self.timeline.append(seg)
            ti.seg, ti.seg_label = seg, label
            if len(self.timeline) > 400:
                del self.timeline[:100]
            self.version += 1

    # ------------------------------------------------------------- threads
    def _spawn(self, ti: ThreadInfo, target) -> None:
        self.tinfo[ti.tid] = ti
        th = threading.Thread(target=self._thread_main, args=(ti, target), name=ti.name, daemon=True)
        self._threads.append(th)
        th.start()

    def _thread_main(self, ti: ThreadInfo, target) -> None:
        ti.native_id = threading.get_native_id()
        try:
            target(ti)
        except Aborted:
            pass
        except Exception as exc:  # pragma: no cover - defensive
            self._log("error", f"Thread {ti.tid} crashed: {exc!r}", ti)
        finally:
            with self.cond:
                ti.state, ti.activity, ti.task, ti.patient, ti.request = "Stopped", "Exited", None, None, None
                self._touch()

    def _start_threads(self) -> None:
        for i in range(self.config["workers"]):
            self._spawn(ThreadInfo(f"T{i + 1}", f"HospitalOS-Worker-{i + 1}", "worker"), self._worker)
        self._spawn(ThreadInfo("ADM", "HospitalOS-Admission", "coordinator"), self._admission)
        self._spawn(ThreadInfo("MON", "HospitalOS-Monitor", "coordinator"), self._monitor)

    def _pause_point(self, ti: ThreadInfo) -> None:
        if not self.paused:
            return
        with self.cond:
            prev, prev_act = ti.state, ti.activity
            ti.state, ti.activity = "Waiting", "Paused"
            self._touch()
        while self.paused:
            if self.stop.is_set():
                raise Aborted("shutdown")
            self.stop.wait(0.05)
        with self.cond:
            ti.state, ti.activity = prev, prev_act
            self._touch()

    def _sleep(self, seconds: float, ti: ThreadInfo) -> None:
        remaining = seconds * self.speed
        while remaining > 0:
            self._pause_point(ti)
            if self.stop.is_set():
                raise Aborted("shutdown")
            step = min(0.05, remaining)
            self.stop.wait(step)
            remaining -= step

    def _admission(self, ti: ThreadInfo) -> None:
        """Coordinator: patient admission and task creation (feeds the shared queue)."""
        for pat in self.patients.values():
            self._sleep(ADMIT_INTERVAL, ti)
            with self.cond:
                task = self.tasks[pat.task_id]
                if pat.registered:
                    continue
                ti.activity = f"Registering {pat.id}"
                self._register(pat, ti)
                self.main_q.put((task.ticket, task))
        with self.cond:
            ti.state, ti.activity = "Idle", "All patients registered"
        self.stop.wait()

    def _register(self, pat: Patient, ti: Optional[ThreadInfo]) -> None:
        pat.registered = True
        self._log("info", f"Patient {pat.id} registered ({pat.urgency}); treatment task {pat.task_id} created", ti)

    def _monitor(self, ti: ThreadInfo) -> None:
        """Coordinator: resource-state monitoring (verifies the allocation invariants)."""
        while not self.stop.wait(0.4):
            with self.cond:
                self.checks += 1
                for r in self.res.values():
                    held = sum(t.held.get(r.key, 0) for t in self.tasks.values())
                    if r.allocated > r.capacity or held != r.allocated:
                        msg = f"Invariant violated on {r.name}"
                        self.violations.append(msg)
                        self._log("error", msg, ti)
                ti.state, ti.activity = "Running", f"Verified invariants ({self.checks} checks)"
                self._touch()

    def _worker(self, ti: ThreadInfo) -> None:
        while not self.stop.is_set():
            self._pause_point(ti)
            with self.cond:
                if ti.state != "Idle":
                    ti.state, ti.activity, ti.task, ti.patient = "Idle", "Waiting for a task on the queue", None, None
                    self._touch()
            item = None
            try:
                item = self.urgent_q.get_nowait()
                urgent = True
            except queue.Empty:
                urgent = False
                if self.hold:
                    self.stop.wait(0.05)
                    continue
                try:
                    item = self.main_q.get(timeout=0.15)
                except queue.Empty:
                    continue
            ticket, task = item
            with self.cond:
                if task.ticket != ticket or task.state != "Waiting":
                    continue  # stale queue entry
                normal = task.scenario is None
                if normal and self.hold:
                    self.deferred.append(item)  # intake frozen for the deadlock demo
                    continue
                if normal:
                    self.in_flight += 1
                task.state, task.thread = "Running", ti.tid
            self._process(task, ti, normal)

    # -------------------------------------------------------- task execution
    def _process(self, task: Task, ti: ThreadInfo, normal: bool) -> None:
        pat = self.patients[task.patient_id]
        outcome = "done"
        try:
            with self.cond:
                ti.state, ti.task, ti.patient, ti.activity = "Running", task.id, pat.id, "Treatment preparation"
                self._log("info", f"Thread {ti.tid} started treatment preparation for {pat.id} ({task.id})", ti)
            if task.scenario:
                self._run_scenario(task, ti, pat)
            else:
                self._run_normal(task, ti, pat)
            with self.cond:
                task.state = "Completed"
                self._log("success", f"Treatment task {task.id} for {pat.id} completed on {ti.tid}", ti)
        except Aborted as exc:
            outcome = str(exc)
        except threading.BrokenBarrierError:
            outcome = "barrier"
        finally:
            with self.cond:
                self._release_all(task, ti, "recovery" if outcome in ("rollback", "terminate") else "info")
                self._seg(ti, task, None)
                if outcome in ("rollback", "barrier"):
                    task.ticket += 1
                    task.scenario, task.state, task.attempts = None, "Waiting", task.attempts + 1
                    self.main_q.put((task.ticket, task))
                    self._log("recovery", f"Task {task.id} rolled back and re-queued for a fresh attempt", ti)
                elif outcome == "terminate":
                    task.state = "Terminated"
                    self._log("recovery", f"Task {task.id} terminated; its patient is flagged for manual follow-up", ti)
                task.thread, task.abort, task.requesting = None, None, None
                if normal:
                    self.in_flight -= 1
                ti.state, ti.task, ti.patient, ti.request, ti.activity = "Idle", None, None, None, "Waiting for a task on the queue"
                self._release_hold_if_done()
                self._check_complete()
                self.cond.notify_all()

    def _run_normal(self, task: Task, ti: ThreadInfo, pat: Patient) -> None:
        self._seg(ti, task, "Preparation")
        self._sleep(PREP_SECONDS, ti)
        for rk in pat.needs:  # fixed global order: a normal workload can wait, but never deadlock
            self._acquire(task, rk, 1, ti)
        with self.cond:
            ti.activity = "Treating " + pat.id
            self._seg(ti, task, "Treatment")
        self._sleep(pat.duration, ti)
        for rk in reversed(list(task.held)):
            self._release(task, rk, ti)

    def _run_scenario(self, task: Task, ti: ThreadInfo, pat: Patient) -> None:
        first, second = ("ventilator", "room") if task.scenario == "A" else ("room", "ventilator")
        self._seg(ti, task, "Preparation")
        self._sleep(0.3, ti)
        self._acquire(task, first, self.res[first].capacity, ti)  # take the whole (exclusive) resource
        with self.cond:
            ti.state, ti.activity = "Waiting", "At barrier (waiting for the other deadlock task)"
            self._log("wait", f"Thread {ti.tid} holds {self.res[first].name} and waits at the barrier", ti)
            self._seg(ti, task, "Barrier wait")
        self.barrier.wait(BARRIER_TIMEOUT)  # both tasks hold their first resource before anyone requests the second
        with self.cond:
            ti.state = "Running"
        self._acquire(task, second, self.res[second].capacity, ti)  # <- circular wait forms here
        with self.cond:
            self._seg(ti, task, "Treatment")
        self._sleep(SCENARIO_TREAT, ti)
        for rk in reversed(list(task.held)):
            self._release(task, rk, ti)

    def _check_complete(self) -> None:
        if self.status == "running" and all(t.state in ("Completed", "Terminated") for t in self.tasks.values()):
            self.status = "completed"
            self._log("success", "All treatment tasks finished - simulation complete")

    def _set_hold(self, hold: bool) -> None:
        with self.cond:
            self.hold = hold
            if not hold:
                for item in self.deferred:
                    self.main_q.put(item)
                self.deferred.clear()
                self.scenario = None
            self._touch()

    def _release_hold_if_done(self) -> None:
        if self.hold and self.scenario == "active":
            live = [t for t in self.tasks.values() if t.scenario and t.state not in ("Completed", "Terminated")]
            if not live:
                self._set_hold(False)

    # --------------------------------------------------------------- controls
    def start(self) -> None:
        with self.cond:
            if self.status != "idle":
                raise ActionError("Simulation already started. Reset it to run again.")
            self.status = "running"
            self._log("info", f"Simulation started with {self.config['workers']} worker threads")
            self._start_threads()

    def pause(self) -> None:
        with self.cond:
            if self.status != "running":
                raise ActionError("Only a running simulation can be paused.")
            self.status, self.paused = "paused", True
            self._log("wait", "Simulation paused (workers stop at their next safe point; blocked tasks stay blocked)")

    def resume(self) -> None:
        with self.cond:
            if self.status != "paused":
                raise ActionError("Simulation is not paused.")
            self.status, self.paused = "running", False
            self._log("info", "Simulation resumed")

    def inject_deadlock(self) -> None:
        with self.cond:
            ctl = self._controls()["inject"]
            if not ctl["enabled"]:
                raise ActionError(ctl["reason"])
            cands = sorted((t for t in self.tasks.values() if t.state == "Waiting" and t.scenario is None), key=lambda t: t.id)[:2]
            if self.status == "idle":
                self.status = "running"
                self._log("info", "Simulation started for the deadlock demonstration")
                self._start_threads()
            self.hold, self.scenario, self.recovery, self.detection = True, "quiescing", None, None
            a, b = cands
            self._log("deadlock", f"Deadlock injection requested: patient intake held while in-flight tasks drain; "
                                  f"{a.id} and {b.id} will be used")
            threading.Thread(target=self._inject_run, args=(a, b), name="HospitalOS-Injector", daemon=True).start()

    def _inject_run(self, a: Task, b: Task) -> None:
        with self.cond:
            self.cond.wait_for(lambda: self.in_flight == 0 or self.stop.is_set(), timeout=60)
            if self.stop.is_set():
                return
            for role, task in (("A", a), ("B", b)):
                pat = self.patients[task.patient_id]
                if not pat.registered:
                    self._register(pat, None)
                task.scenario = role
                task.ticket += 1
            self.barrier = threading.Barrier(2)
            self.scenario = "active"
            self._log("deadlock", f"Scenario: {a.id} takes the ventilators first, {b.id} takes the procedure rooms first; "
                                  f"then each requests the other's resource")
            self.urgent_q.put((a.ticket, a))
            self.urgent_q.put((b.ticket, b))

    def reset(self) -> None:
        self._shutdown()
        with self.cond:
            self._build(self.config)
            self._log("info", "Simulation reset")

    def apply_config(self, raw: Dict[str, Any]) -> None:
        cfg = validate_config(raw)
        self._shutdown()
        with self.cond:
            self._build(cfg)
            self._log("info", "Configuration applied - simulation reset with a new scenario")

    def _shutdown(self) -> None:
        with self.cond:
            self.stop.set()
            for ti in self.tinfo.values():
                if ti.state != "Stopped":
                    ti.state = "Stopping"
            if self.barrier is not None:
                try:
                    self.barrier.abort()
                except Exception:
                    pass
            self.cond.notify_all()
        for th in self._threads:
            th.join(timeout=3)
        self._threads = []

    def shutdown(self) -> None:
        self._shutdown()

    # ------------------------------------------------------------- detection
    def detect(self) -> Dict[str, Any]:
        with self.cond:
            det = self._detect_locked()
            self.detection = det
            if det["deadlock"]:
                self._log("deadlock", "Deadlock detector found a circular wait: " + " -> ".join(
                    f"{c['task']}" for c in det["cycle"]) + f" -> {det['cycle'][0]['task']}")
            else:
                self._log("info", "Deadlock detector ran: " + det["explanation"])
            return det

    def _detect_locked(self) -> Dict[str, Any]:
        """Reduction (multi-instance safe) to find deadlocked tasks, then a wait-for-graph cycle for display."""
        blocked = {t.id: t for t in self.tasks.values() if t.state == "Blocked" and t.requesting}
        work = {k: r.available for k, r in self.res.items()}
        for t in self.tasks.values():
            if t.id not in blocked:  # running tasks will finish and release what they hold
                for k, u in t.held.items():
                    work[k] += u
        pending = set(blocked)
        progress = True
        while progress:
            progress = False
            for tid in sorted(pending):
                k, u = blocked[tid].requesting  # type: ignore[misc]
                if u <= work[k]:
                    pending.discard(tid)
                    for kk, uu in blocked[tid].held.items():
                        work[kk] += uu
                    progress = True
        dead = sorted(pending)
        at = time.strftime("%H:%M:%S")
        if not dead:
            expl = (f"No circular wait. {len(blocked)} task(s) are waiting for busy resources, but each is waiting on a "
                    "task that can still finish and release them - ordinary waiting, not deadlock."
                    if blocked else "No circular wait. No treatment task is blocked on a resource.")
            return {"deadlock": False, "tasks": [], "cycle": [], "edges": [], "explanation": expl, "at": at}
        edges: Dict[str, List[Tuple[str, str]]] = {}
        for tid in dead:
            rk = blocked[tid].requesting[0]  # type: ignore[index]
            edges[tid] = [(o, rk) for o in self.res[rk].owners if o != tid and o in pending]
        cyc = self._find_cycle(edges) or dead
        cycle = []
        for i, u in enumerate(cyc):
            v = cyc[(i + 1) % len(cyc)]
            rk = blocked[u].requesting[0]  # type: ignore[index]
            cycle.append({"task": u, "patient": self.tasks[u].patient_id, "waits_for": rk, "resource": self.res[rk].name,
                          "held_by": v, "holder_patient": self.tasks[v].patient_id})
        parts = []
        for c in cycle:
            holds = ", ".join(self.res[k].name for k in self.tasks[c["task"]].held) or "nothing"
            parts.append(f"{c['task']} ({c['patient']}) holds {holds} and waits for {c['resource']} held by {c['held_by']}")
        expl = ("; ".join(parts) + ". Each task needs a resource that only another task in the cycle can release, and "
                "resources cannot be taken away, so none of them can ever proceed (circular wait).")
        return {"deadlock": True, "tasks": dead, "cycle": cycle,
                "edges": [{"from": u, "to": v, "resource": rk} for u, es in edges.items() for v, rk in es],
                "explanation": expl, "at": at}

    @staticmethod
    def _find_cycle(edges: Dict[str, List[Tuple[str, str]]]) -> Optional[List[str]]:
        color: Dict[str, int] = {}
        stack: List[str] = []

        def dfs(u: str) -> Optional[List[str]]:
            color[u] = 1
            stack.append(u)
            for v, _ in edges.get(u, []):
                if color.get(v) == 1:
                    return stack[stack.index(v):]
                if v not in color:
                    found = dfs(v)
                    if found:
                        return found
            stack.pop()
            color[u] = 2
            return None

        for n in sorted(edges):
            if n not in color:
                found = dfs(n)
                if found:
                    return found
        return None

    # -------------------------------------------------------------- recovery
    def _brief(self, involved: List[str]) -> Dict[str, Any]:
        return {
            "resources": {k: {"name": r.name, "capacity": r.capacity, "owners": dict(r.owners),
                              "waiting": [w[0] for w in r.waiting]} for k, r in self.res.items()},
            "tasks": {t.id: {"patient": t.patient_id, "state": t.state,
                             "held": [self.res[k].name for k in t.held],
                             "requesting": self.res[t.requesting[0]].name if t.requesting else None}
                      for t in self.tasks.values() if t.id in involved},
        }

    def recover(self, task_id: str, mode: str = "rollback") -> Dict[str, Any]:
        if mode not in ("rollback", "terminate"):
            raise ActionError("Recovery mode must be 'rollback' or 'terminate'.")
        with self.cond:
            det = self._detect_locked()
            if not det["deadlock"]:
                raise ActionError("No deadlock exists, so there is nothing to recover. Run Detect Deadlock first.")
            if task_id not in det["tasks"]:
                raise ActionError(f"{task_id} is not part of the deadlock. Choose one of: {', '.join(det['tasks'])}.")
            involved = det["tasks"]
            victim = self.tasks[task_id]
            before = self._brief(involved)
            self._log("recovery", f"Recovery initiated: {mode} of {task_id} ({victim.patient_id})")
            victim.abort = mode
            released = self._release_all(victim, None, "recovery")
            for r in self.res.values():
                r.waiting = [w for w in r.waiting if w[0] != victim.id]
            victim.requesting = None
            self._log("recovery", f"Resources released: {', '.join(released) or 'none'}")
            self.cond.notify_all()
            self.cond.wait_for(lambda: all(self.tasks[t].state != "Blocked" for t in involved), timeout=3.0)
            survivors = [t for t in involved if t != task_id]
            resumed = [t for t in survivors if self.tasks[t].state != "Blocked"]
            for t in resumed:
                self._log("recovery", f"Eligible blocked task {t} resumed execution")
            if self.hold:
                self._set_hold(False)
            after = self._brief(involved)
            verb = "rolled back and re-queued" if mode == "rollback" else "terminated"
            msg = (f"{task_id} ({victim.patient_id}) was {verb}; released {', '.join(released) or 'nothing'}. "
                   f"{', '.join(resumed) or 'No task'} resumed. Circular wait removed.")
            self.recovery = {"victim": task_id, "mode": mode, "message": msg, "before": before, "after": after,
                             "released": released, "resumed": resumed}
            self.detection = None
            self._log("success", "Recovery complete: " + msg)
            return self.recovery

    # ---------------------------------------------------------------- views
    def _controls(self) -> Dict[str, Dict[str, Any]]:
        def c(ok: Any, reason: str = "") -> Dict[str, Any]:
            return {"enabled": bool(ok), "reason": "" if ok else reason}

        st = self.status
        cands = [t for t in self.tasks.values() if t.state == "Waiting" and t.scenario is None]
        if st not in ("idle", "running"):
            inj = c(False, "Deadlock can only be injected while idle or running (resume or reset first).")
        elif self.scenario is not None:
            inj = c(False, "A deadlock demonstration is already in progress. Detect and recover, or reset.")
        elif len(cands) < 2:
            inj = c(False, "Needs at least two patients that have not started treatment. Reset to repeat.")
        else:
            inj = c(True)
        return {
            "start": c(st == "idle", "Already started. Reset to run again."),
            "pause": c(st == "running", "Only a running simulation can be paused."),
            "resume": c(st == "paused", "The simulation is not paused."),
            "inject": inj,
            "detect": c(st != "idle", "Start the simulation or inject a deadlock first."),
            "recover": c(self.detection and self.detection["deadlock"], "Run Detect Deadlock and find a circular wait first."),
            "reset": c(True),
        }

    def snapshot(self) -> Dict[str, Any]:
        with self.cond:
            now = round(time.time() - self.t0, 3)
            tasks = list(self.tasks.values())
            held_names = lambda t: {self.res[k].name: u for k, u in t.held.items()}  # noqa: E731
            patients = []
            for p in self.patients.values():
                t = self.tasks[p.task_id]
                patients.append({
                    "id": p.id, "urgency": p.urgency, "state": t.state, "task": t.id, "thread": t.thread,
                    "needs": [RES_NAMES[k] for k in p.needs], "held": held_names(t), "attempts": t.attempts,
                    "registered": p.registered, "scenario": t.scenario,
                    "requesting": {"resource": self.res[t.requesting[0]].name, "units": t.requesting[1]} if t.requesting else None})
            owner = lambda tid: self.tasks[tid].patient_id  # noqa: E731
            resources = [{
                "key": r.key, "name": r.name, "capacity": r.capacity, "allocated": r.allocated, "available": r.available,
                "owners": [{"task": tid, "patient": owner(tid), "units": u} for tid, u in r.owners.items()],
                "waiting": [{"task": tid, "patient": owner(tid), "units": u} for tid, u in r.waiting]}
                for r in self.res.values()]
            threads = [{"id": ti.tid, "name": ti.name, "role": ti.role, "state": ti.state, "task": ti.task,
                        "patient": ti.patient, "activity": ti.activity, "native_id": ti.native_id,
                        "request": dict(ti.request) if ti.request else None} for ti in self.tinfo.values()]
            count = lambda s: sum(1 for t in tasks if t.state == s)  # noqa: E731
            involved = [t for t in tasks if t.held or (t.state == "Blocked" and t.requesting)]
            det = self.detection
            graph = {
                "resources": [{"key": r.key, "name": r.name, "capacity": r.capacity, "allocated": r.allocated} for r in self.res.values()],
                "tasks": [{"id": t.id, "patient": t.patient_id, "state": t.state, "thread": t.thread, "held": held_names(t),
                           "requesting": self.res[t.requesting[0]].name if t.requesting else None} for t in involved],
                "allocation": [{"resource": r.key, "task": tid, "units": u} for r in self.res.values() for tid, u in r.owners.items()],
                "requests": [{"task": t.id, "resource": t.requesting[0], "units": t.requesting[1]} for t in tasks if t.requesting],
                "deadlocked": det["tasks"] if det and det["deadlock"] else []}
            return {
                "version": self.version, "now": now, "status": self.status, "config": dict(self.config),
                "defaults": DEFAULTS, "limits": LIMITS, "controls": self._controls(),
                "scenario": self.scenario, "dispatch_hold": self.hold,
                "metrics": {"total": len(tasks), "waiting": count("Waiting"), "running": count("Running"),
                            "blocked": count("Blocked"), "completed": count("Completed"), "terminated": count("Terminated"),
                            "available_units": sum(r.available for r in self.res.values()),
                            "occupied_units": sum(r.allocated for r in self.res.values())},
                "patients": patients, "resources": resources, "threads": threads, "graph": graph,
                "timeline": [dict(s, end=s["end"]) for s in self.timeline[-250:]],
                "events": list(self.events)[-120:], "detection": det, "recovery": self.recovery,
                "sync": {"queue_depth": self.main_q.qsize(), "urgent_depth": self.urgent_q.qsize(),
                         "in_flight": self.in_flight, "checks": self.checks, "violations": len(self.violations),
                         "deferred": len(self.deferred)},
            }
