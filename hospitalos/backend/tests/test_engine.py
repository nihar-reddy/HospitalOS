"""Automated tests for the HospitalOS engine. Run:  python -m unittest discover -s tests -v  (or pytest)."""
import os
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import ActionError, ConfigError, DEFAULTS, Engine, OwnershipError, ThreadInfo, validate_config  # noqa: E402


def wait_until(fn, timeout=15.0, step=0.02):
    end = time.time() + timeout
    while time.time() < end:
        if fn():
            return True
        time.sleep(step)
    return False


class EngineCase(unittest.TestCase):
    speed = 0.3

    def make(self, **cfg):
        e = Engine({**DEFAULTS, **cfg}, speed=self.speed)
        self.addCleanup(e.shutdown)
        return e

    def blocked_pair(self, e):
        return wait_until(lambda: e.snapshot()["metrics"]["blocked"] >= 2)


class TestConfig(EngineCase):
    def test_defaults_valid(self):
        self.assertEqual(validate_config(DEFAULTS), DEFAULTS)

    def test_invalid_values_rejected(self):
        for bad in ({"beds": 0}, {"beds": -1}, {"workers": 1}, {"workers": 99}, {"patients": 2.5},
                    {"rooms": "3"}, {"ventilators": True}, {"extra": 1}):
            with self.assertRaises(ConfigError, msg=str(bad)):
                validate_config({**DEFAULTS, **bad})

    def test_scenario_is_reproducible(self):
        a, b = self.make(), self.make()
        self.assertEqual([(p["urgency"], p["needs"]) for p in a.snapshot()["patients"]],
                         [(p["urgency"], p["needs"]) for p in b.snapshot()["patients"]])

    def test_apply_config_changes_worker_count(self):
        e = self.make()
        e.apply_config({**DEFAULTS, "workers": 3, "patients": 4})
        e.start()
        snap = e.snapshot()
        self.assertEqual(len([t for t in snap["threads"] if t["role"] == "worker"]), 3)
        self.assertEqual(snap["metrics"]["total"], 4)
        with self.assertRaises(ConfigError):
            e.apply_config({**DEFAULTS, "beds": 0})


class TestSynchronization(EngineCase):
    def test_capacity_never_exceeded_under_contention(self):
        e = self.make(ventilators=2, patients=12, workers=4)
        tasks = list(e.tasks.values())
        peak, errors = [0], []

        def hammer(task, n):
            ti = ThreadInfo(f"X{n}", f"x{n}", "worker")
            try:
                for _ in range(40):
                    e._acquire(task, "ventilator", 1, ti)
                    peak[0] = max(peak[0], e.res["ventilator"].allocated)
                    e._release(task, "ventilator", ti)
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        ths = [threading.Thread(target=hammer, args=(t, i)) for i, t in enumerate(tasks)]
        [t.start() for t in ths]
        [t.join(30) for t in ths]
        self.assertEqual(errors, [])
        self.assertLessEqual(peak[0], 2)
        self.assertEqual(e.res["ventilator"].allocated, 0)
        self.assertEqual(e.violations, [])

    def test_only_owner_can_release(self):
        e = self.make()
        t1, t2 = e.tasks["TASK-001"], e.tasks["TASK-002"]
        ti = ThreadInfo("X", "x", "worker")
        e._acquire(t1, "bed", 1, ti)
        with self.assertRaises(OwnershipError):
            e._release(t2, "bed", ti)
        e._release(t1, "bed", ti)


class TestFullRun(EngineCase):
    def test_concurrent_execution_completes_without_false_deadlock(self):
        e = self.make()
        e.start()
        false_positive = False
        while e.snapshot()["status"] != "completed":
            if e.detect()["deadlock"]:
                false_positive = True
            time.sleep(0.03)
            self.assertLess(e.snapshot()["now"], 60, "simulation did not finish")
        self.assertFalse(false_positive, "ordinary waiting must not be reported as deadlock")
        snap = e.snapshot()
        self.assertEqual(snap["metrics"]["completed"], 6)
        segs = [s for s in snap["timeline"] if s["end"] is not None]
        overlap = any(a["thread"] != b["thread"] and a["start"] < b["end"] and b["start"] < a["end"]
                      for i, a in enumerate(segs) for b in segs[i + 1:])
        self.assertTrue(overlap, "different worker threads must have overlapping activity")
        self.assertGreaterEqual(len({s["thread"] for s in segs}), 2)
        self.assertEqual(snap["sync"]["violations"], 0)
        for r in snap["resources"]:
            self.assertEqual(r["allocated"], 0)

    def test_pause_and_resume(self):
        e = self.make()
        e.start()
        wait_until(lambda: e.snapshot()["metrics"]["running"] >= 1)
        e.pause()
        time.sleep(0.5)  # let in-flight work reach a pause point
        done = e.snapshot()["metrics"]["completed"]
        time.sleep(0.8)
        self.assertEqual(e.snapshot()["metrics"]["completed"], done)
        self.assertEqual(e.snapshot()["status"], "paused")
        with self.assertRaises(ActionError):
            e.start()
        e.resume()
        self.assertTrue(wait_until(lambda: e.snapshot()["status"] == "completed", 60))

    def test_reset_is_clean_and_repeatable(self):
        e = self.make()
        e.start()
        time.sleep(0.4)
        e.reset()
        snap = e.snapshot()
        self.assertEqual(snap["status"], "idle")
        self.assertTrue(all(p["state"] == "Waiting" for p in snap["patients"]))
        self.assertEqual(snap["metrics"]["occupied_units"], 0)
        self.assertFalse([t for t in threading.enumerate() if t.name.startswith("HospitalOS-Worker")])
        e.start()
        self.assertTrue(wait_until(lambda: e.snapshot()["status"] == "completed", 60))


class TestDeadlock(EngineCase):
    def test_inject_detect_recover_rollback(self):
        e = self.make()
        e.inject_deadlock()
        self.assertTrue(self.blocked_pair(e), "two tasks should become blocked")
        # backend stays responsive while deadlocked
        t = time.time()
        for _ in range(20):
            e.snapshot()
        self.assertLess(time.time() - t, 1.0)

        snap = e.snapshot()
        blocked = {p["task"]: p for p in snap["patients"] if p["state"] == "Blocked"}
        self.assertEqual(set(blocked), {"TASK-001", "TASK-002"})
        self.assertEqual(blocked["TASK-001"]["requesting"]["resource"], "Procedure Rooms")
        self.assertEqual(blocked["TASK-002"]["requesting"]["resource"], "Ventilators")
        self.assertEqual(len([x for x in snap["threads"] if x["state"] == "Blocked"]), 2)
        self.assertFalse(snap["controls"]["recover"]["enabled"])  # must detect first

        det = e.detect()
        self.assertTrue(det["deadlock"])
        self.assertEqual(sorted(det["tasks"]), ["TASK-001", "TASK-002"])
        self.assertEqual({c["resource"] for c in det["cycle"]}, {"Ventilators", "Procedure Rooms"})
        self.assertTrue(e.snapshot()["controls"]["recover"]["enabled"])
        with self.assertRaises(ActionError):
            e.recover("TASK-005")

        rec = e.recover("TASK-001", "rollback")
        self.assertEqual(rec["resumed"], ["TASK-002"])
        self.assertEqual(rec["before"]["tasks"]["TASK-002"]["state"], "Blocked")
        self.assertNotEqual(rec["after"]["tasks"]["TASK-002"]["state"], "Blocked")
        self.assertFalse(e.detect()["deadlock"])
        self.assertTrue(wait_until(lambda: e.snapshot()["status"] == "completed", 60))
        snap = e.snapshot()
        self.assertEqual(snap["metrics"]["completed"], 6)  # victim re-ran after rollback
        self.assertEqual(snap["sync"]["violations"], 0)

    def test_recover_by_terminate(self):
        e = self.make(patients=4)
        e.inject_deadlock()
        self.assertTrue(self.blocked_pair(e))
        e.detect()
        e.recover("TASK-002", "terminate")
        self.assertTrue(wait_until(lambda: e.snapshot()["status"] == "completed", 60))
        m = e.snapshot()["metrics"]
        self.assertEqual((m["completed"], m["terminated"]), (3, 1))

    def test_inject_while_running_and_repeatable(self):
        e = self.make(patients=8)
        e.start()
        wait_until(lambda: e.snapshot()["metrics"]["running"] >= 1)
        e.inject_deadlock()
        self.assertTrue(self.blocked_pair(e))
        self.assertTrue(e.detect()["deadlock"])
        with self.assertRaises(ActionError):
            e.inject_deadlock()  # already in progress
        e.recover(e.detect()["tasks"][0])
        self.assertTrue(wait_until(lambda: e.snapshot()["status"] == "completed", 60))
        e.reset()
        e.inject_deadlock()  # repeat after reset
        self.assertTrue(self.blocked_pair(e))
        self.assertTrue(e.detect()["deadlock"])

    def test_capacity_greater_than_one_still_deadlocks(self):
        e = self.make(ventilators=3, rooms=2)
        e.inject_deadlock()
        self.assertTrue(self.blocked_pair(e))
        self.assertTrue(e.detect()["deadlock"])

    def test_detect_with_no_blockage(self):
        e = self.make()
        e.start()
        self.assertFalse(e.detect()["deadlock"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
