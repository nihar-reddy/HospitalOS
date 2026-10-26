"""HospitalOS FastAPI app: REST controls + WebSocket live state. All logic lives in engine.py."""
import asyncio
import time
from typing import Any, Dict

from fastapi import Body, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from engine import DEFAULTS, ActionError, ConfigError, Engine

app = FastAPI(title="HospitalOS")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])
engine = Engine()


def run(fn, message: str, *args):
    """Run an engine action; map domain errors to HTTP errors. Routes are sync -> executed in a worker pool."""
    try:
        result = fn(*args)
    except ConfigError as exc:
        raise HTTPException(422, str(exc))
    except ActionError as exc:
        raise HTTPException(409, str(exc))
    return {"ok": True, "message": message if not isinstance(result, dict) or "message" not in result else result["message"],
            "state": engine.snapshot()}


@app.get("/api/state")
def state():
    return engine.snapshot()


@app.post("/api/config")
def config(payload: Dict[str, Any] = Body(...)):
    return run(engine.apply_config, "Configuration applied. Simulation reset with a new scenario.", payload)


@app.post("/api/config/defaults")
def config_defaults():
    return run(engine.apply_config, "Default configuration restored.", dict(DEFAULTS))


@app.post("/api/start")
def start():
    return run(engine.start, "Simulation started.")


@app.post("/api/pause")
def pause():
    return run(engine.pause, "Simulation paused.")


@app.post("/api/resume")
def resume():
    return run(engine.resume, "Simulation resumed.")


@app.post("/api/inject")
def inject():
    return run(engine.inject_deadlock, "Deadlock injection started: intake is held while the scenario is set up.")


@app.post("/api/detect")
def detect():
    def _d():
        det = engine.detect()
        return {"message": ("Deadlock detected: " if det["deadlock"] else "") + det["explanation"]}
    return run(_d, "")


@app.post("/api/recover")
def recover(payload: Dict[str, Any] = Body(...)):
    return run(lambda: engine.recover(str(payload.get("task_id", "")), str(payload.get("mode", "rollback"))), "")


@app.post("/api/reset")
def reset():
    return run(engine.reset, "Simulation reset.")


@app.websocket("/ws")
async def ws_state(ws: WebSocket):
    await ws.accept()
    last, sent = -1, 0.0
    try:
        while True:
            if engine.version != last or time.time() - sent > 1.0:
                snap = engine.snapshot()
                await ws.send_json(snap)
                last, sent = snap["version"], time.time()
            await asyncio.sleep(0.12)
    except (WebSocketDisconnect, RuntimeError):
        pass


@app.on_event("shutdown")
def _shutdown():
    engine.shutdown()
