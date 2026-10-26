import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from fastapi.testclient import TestClient
    import main
except Exception:  # fastapi/httpx not installed
    TestClient = None


@unittest.skipIf(TestClient is None, "fastapi/httpx not installed")
class TestApi(unittest.TestCase):
    def test_flow_and_websocket(self):
        c = TestClient(main.app)
        c.post("/api/reset")
        self.assertEqual(c.post("/api/config", json={"patients": 6, "beds": 0, "ventilators": 1, "rooms": 1, "workers": 4}).status_code, 422)
        self.assertEqual(c.post("/api/detect").status_code, 409)
        self.assertEqual(c.post("/api/inject").status_code, 200)
        for _ in range(100):
            if c.get("/api/state").json()["metrics"]["blocked"] >= 2:
                break
            time.sleep(0.1)
        self.assertEqual(c.post("/api/detect").json()["state"]["detection"]["deadlock"], True)
        with c.websocket_connect("/ws") as ws:
            self.assertEqual(ws.receive_json()["detection"]["deadlock"], True)
        r = c.post("/api/recover", json={"task_id": "TASK-001", "mode": "rollback"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["state"]["recovery"]["resumed"])
        c.post("/api/reset")


if __name__ == "__main__":
    unittest.main()
