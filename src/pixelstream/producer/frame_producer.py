import base64
import time
import uuid
from typing import Any

import cv2
import numpy as np
import structlog
from confluent_kafka import Producer

from pixelstream.config import settings
from pixelstream.schemas import FrameMessage

log = structlog.get_logger()

TARGET_WIDTH = 640
TARGET_HEIGHT = 480
JPEG_QUALITY = 80


def encode_frame(frame: np.ndarray) -> bytes:
    """Resize to 640×480 and encode as JPEG at quality 80. Returns raw bytes."""
    frame = cv2.resize(frame, (TARGET_WIDTH, TARGET_HEIGHT))
    _, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    return jpg.tobytes()


class FrameProducer:
    def __init__(
        self,
        source: str = settings.video_source,
        topic: str = "ps.frames",
        target_fps: int = settings.target_fps,
        loop: bool = True,
    ) -> None:
        self._source = source
        self._topic = topic
        self._target_fps = target_fps
        self._loop = loop
        self._producer = Producer(
            {
                "bootstrap.servers": settings.kafka_bootstrap,
                "client.id": "pixelstream-producer",
                "queue.buffering.max.ms": 100,
            }
        )

    def start(self) -> None:
        cap = cv2.VideoCapture(self._source)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video source: {self._source!r}")

        frame_delay = 1.0 / self._target_fps
        log.info("producer_started", source=self._source, fps=self._target_fps, topic=self._topic)

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    if self._loop:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    log.info("video_ended", source=self._source)
                    break

                jpg_bytes = encode_frame(frame)
                msg = FrameMessage(
                    frame_id=str(uuid.uuid4()),
                    timestamp=time.time(),
                    source_id=self._source,
                    frame_b64=base64.b64encode(jpg_bytes).decode(),
                    width=TARGET_WIDTH,
                    height=TARGET_HEIGHT,
                )
                self._producer.produce(
                    self._topic,
                    key=msg.frame_id.encode(),
                    value=msg.model_dump_json().encode(),
                    callback=self._on_delivery,
                )
                self._producer.poll(0)
                log.debug("frame_published", frame_id=msg.frame_id[:8], size_bytes=len(jpg_bytes))
                time.sleep(frame_delay)
        finally:
            cap.release()
            self._producer.flush(timeout=5)
            log.info("producer_stopped")

    def _on_delivery(self, err: Any, msg: Any) -> None:
        if err:
            log.error("delivery_failed", error=str(err), topic=msg.topic())


def main() -> None:
    producer = FrameProducer()
    producer.start()


if __name__ == "__main__":
    main()
