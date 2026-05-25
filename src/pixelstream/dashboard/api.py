import asyncio
import json
import pathlib
import time

import structlog
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pixelstream.config import settings
from pixelstream.dashboard.broadcaster import Broadcaster

log = structlog.get_logger()

app = FastAPI(title="PixelStream API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_broadcaster = Broadcaster(settings.kafka_bootstrap)
_start_time = time.time()
_stats: dict = {
    "total_frames": 0,
    "total_detections": 0,
    "active_model": settings.default_model,
    "fps": 0.0,
}

# Written by producer/spark side to update frame/detection counts from ps.detections messages
_MODEL_STATE_FILE = pathlib.Path("data/model_state.json")


class ModelSwitch(BaseModel):
    model: str


@app.on_event("startup")
async def _startup() -> None:
    asyncio.create_task(_broadcaster.run())
    asyncio.create_task(_stats_updater())


@app.get("/api/stats")
async def get_stats() -> dict:
    return {**_stats, "uptime_seconds": round(time.time() - _start_time)}


@app.post("/api/model")
async def switch_model(body: ModelSwitch) -> dict:
    valid = {"yolov11n", "rtdetr-l"}
    if body.model not in valid:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=f"model must be one of {valid}")
    _MODEL_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _MODEL_STATE_FILE.write_text(json.dumps({"model": body.model}))
    _stats["active_model"] = body.model
    log.info("model_switch_requested", model=body.model)
    return {"model": body.model, "status": "switching"}


@app.websocket("/ws/detections")
async def ws_detections(ws: WebSocket) -> None:
    await ws.accept()
    q = _broadcaster.subscribe()
    log.info("ws_connected", clients=len(_broadcaster._clients))
    try:
        while True:
            payload = await asyncio.wait_for(q.get(), timeout=30.0)
            await ws.send_text(payload)
            # Update running stats from each detection message
            try:
                data = json.loads(payload)
                _stats["total_frames"] += 1
                _stats["total_detections"] += len(data.get("detections", []))
            except Exception:
                pass
    except (WebSocketDisconnect, TimeoutError):
        pass
    finally:
        _broadcaster.unsubscribe(q)
        log.info("ws_disconnected", clients=len(_broadcaster._clients))


async def _stats_updater() -> None:
    """Compute a rolling FPS estimate every 5 seconds."""
    prev_frames = 0
    while True:
        await asyncio.sleep(5)
        delta = _stats["total_frames"] - prev_frames
        _stats["fps"] = round(delta / 5, 1)
        prev_frames = _stats["total_frames"]


def main() -> None:
    uvicorn.run(
        "pixelstream.dashboard.api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
