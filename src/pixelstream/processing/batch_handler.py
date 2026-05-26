import base64
import json
import pathlib
import time
from typing import Any

import cv2
import numpy as np

import structlog
from confluent_kafka import Producer
from pyspark.sql import DataFrame

from pixelstream.config import settings
from pixelstream.inference.base import InferenceBackend
from pixelstream.schemas import DetectionResult, FrameMessage
from pixelstream.storage.delta_writer import DeltaWriter

log = structlog.get_logger()

# FastAPI writes {"model": "yolov11n"} here when user clicks the toggle
_MODEL_STATE_FILE = pathlib.Path("data/model_state.json")


class BatchHandler:
    def __init__(self, backend: InferenceBackend, writer: DeltaWriter) -> None:
        self._backend = backend
        self._writer = writer
        self._producer = Producer(
            {"bootstrap.servers": settings.kafka_bootstrap, "client.id": "pixelstream-spark"}
        )

    def handle(self, batch_df: DataFrame, batch_id: int) -> None:
        self._apply_pending_model_switch()

        rows = batch_df.collect()
        if not rows:
            log.debug("empty_batch", batch_id=batch_id)
            return

        log.info("batch_received", batch_id=batch_id, rows=len(rows))
        results: list[DetectionResult] = []

        for row in rows:
            try:
                result = self._process_row(row)
                if result is not None:
                    results.append(result)
            except Exception as exc:
                log.error("frame_failed", error=str(exc), batch_id=batch_id)

        if results:
            self._writer.write(results)
            self._publish_detections(results)

        total_det = sum(len(r.detections) for r in results)
        log.info("batch_done", batch_id=batch_id, processed=len(results), detections=total_det)

    def _process_row(self, row: Any) -> DetectionResult | None:
        if row.value is None:
            return None
        msg = FrameMessage.model_validate_json(row.value.decode())
        frame_bytes = base64.b64decode(msg.frame_b64)

        t0 = time.perf_counter()
        detections = self._backend.detect(frame_bytes)
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        return DetectionResult(
            frame_id=msg.frame_id,
            timestamp=msg.timestamp,
            model=self._backend.model_name,
            latency_ms=latency_ms,
            detections=detections,
            thumbnail_b64=_make_thumbnail(frame_bytes),
        )


def _make_thumbnail(frame_bytes: bytes) -> str | None:
    """Decode JPEG, resize to 320×240, re-encode as small JPEG for browser."""
    try:
        arr = np.frombuffer(frame_bytes, np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return None
        thumb = cv2.resize(frame, (320, 240))
        ok, buf = cv2.imencode(".jpg", thumb, [cv2.IMWRITE_JPEG_QUALITY, 60])
        if not ok:
            return None
        return base64.b64encode(buf.tobytes()).decode()
    except Exception:
        return None

    def _publish_detections(self, results: list[DetectionResult]) -> None:
        for result in results:
            self._producer.produce(
                "ps.detections",
                key=result.frame_id.encode(),
                value=result.model_dump_json().encode(),
            )
        self._producer.flush(timeout=3)

    def _apply_pending_model_switch(self) -> None:
        try:
            if not _MODEL_STATE_FILE.exists():
                return
            state = json.loads(_MODEL_STATE_FILE.read_text())
            requested = state.get("model", "")
            if requested and requested != self._backend.model_name:
                self._backend.switch_model(requested)
                log.info("model_switch_applied", model=requested)
        except Exception as exc:
            log.warning("model_switch_check_failed", error=str(exc))
