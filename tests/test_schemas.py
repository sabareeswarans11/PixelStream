import pytest
from pydantic import ValidationError

from pixelstream.schemas import Detection, DetectionResult, FrameMessage


def test_frame_message_roundtrip():
    msg = FrameMessage(
        frame_id="abc-123",
        timestamp=1_700_000_000.0,
        source_id="data/sample.mp4",
        frame_b64="aGVsbG8=",
        width=640,
        height=480,
    )
    restored = FrameMessage.model_validate_json(msg.model_dump_json())
    assert restored.frame_id == msg.frame_id
    assert restored.width == 640


def test_detection_confidence_validator():
    with pytest.raises(ValidationError):
        Detection(cls="person", confidence=1.5, bbox=[0.1, 0.1, 0.4, 0.4])


def test_detection_bbox_length_validator():
    with pytest.raises(ValidationError):
        Detection(cls="person", confidence=0.9, bbox=[0.1, 0.2])


def test_detection_result_roundtrip():
    dr = DetectionResult(
        frame_id="f1",
        timestamp=1.0,
        model="yolov11n",
        latency_ms=55.0,
        detections=[Detection(cls="car", confidence=0.88, bbox=[0.1, 0.1, 0.5, 0.5])],
    )
    restored = DetectionResult.model_validate_json(dr.model_dump_json())
    assert restored.detections[0].cls == "car"
    assert restored.latency_ms == 55.0
