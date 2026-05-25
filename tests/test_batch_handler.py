import base64

import numpy as np

from pixelstream.inference.mock import MockBackend
from pixelstream.schemas import FrameMessage


def _make_frame_message() -> FrameMessage:
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    import cv2

    _, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return FrameMessage(
        frame_id="test-frame-001",
        timestamp=1_700_000_000.0,
        source_id="test",
        frame_b64=base64.b64encode(jpg.tobytes()).decode(),
        width=640,
        height=480,
    )


def test_process_row_returns_detection_result():
    """BatchHandler._process_row should return a DetectionResult with mock backend."""
    from pixelstream.processing.batch_handler import BatchHandler

    class FakeWriter:
        def write(self, results):
            pass

        def read_recent(self, limit=200):
            return []

    handler = BatchHandler(backend=MockBackend(), writer=FakeWriter())

    class FakeRow:
        value = _make_frame_message().model_dump_json().encode()

    result = handler._process_row(FakeRow())
    assert result is not None
    assert result.frame_id == "test-frame-001"
    assert result.model == "mock"
    assert result.latency_ms >= 0
    assert len(result.detections) >= 1


def test_process_row_none_value_returns_none():
    from pixelstream.processing.batch_handler import BatchHandler

    class FakeWriter:
        def write(self, results):
            pass

    handler = BatchHandler(backend=MockBackend(), writer=FakeWriter())

    class NullRow:
        value = None

    assert handler._process_row(NullRow()) is None
