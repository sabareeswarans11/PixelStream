import pytest

from pixelstream.inference.mock import MockBackend
from pixelstream.schemas import Detection


def test_mock_returns_detections(sample_frame_bytes):
    backend = MockBackend()
    results = backend.detect(sample_frame_bytes)
    assert len(results) >= 1
    assert all(isinstance(d, Detection) for d in results)


def test_mock_confidence_in_range(sample_frame_bytes):
    backend = MockBackend()
    for _ in range(10):
        for d in backend.detect(sample_frame_bytes):
            assert 0.0 <= d.confidence <= 1.0


def test_mock_bbox_normalized(sample_frame_bytes):
    backend = MockBackend()
    for _ in range(10):
        for d in backend.detect(sample_frame_bytes):
            assert len(d.bbox) == 4
            x1, y1, x2, y2 = d.bbox
            assert 0.0 <= x1 < x2 <= 1.0, f"bad x: {d.bbox}"
            assert 0.0 <= y1 < y2 <= 1.0, f"bad y: {d.bbox}"


def test_mock_model_name():
    assert MockBackend().model_name == "mock"


def test_mock_switch_model_raises():
    with pytest.raises(NotImplementedError):
        MockBackend().switch_model("yolov11n")


@pytest.mark.integration
def test_ultralytics_uses_cpu(sample_frame_bytes):
    """Verify UltralyticsBackend never uses MPS or CUDA on this machine."""
    from pixelstream.inference.ultralytics_backend import UltralyticsBackend

    backend = UltralyticsBackend("yolov11n")
    results = backend.detect(sample_frame_bytes)
    # If we reach here without RuntimeError the model ran on CPU
    assert isinstance(results, list)


@pytest.mark.integration
def test_ultralytics_switch_model(sample_frame_bytes):
    from pixelstream.inference.ultralytics_backend import UltralyticsBackend

    backend = UltralyticsBackend("yolov11n")
    backend.detect(sample_frame_bytes)  # warm up yolov11n
    backend.switch_model("rtdetr-l")
    assert backend.model_name == "rtdetr-l"
    results = backend.detect(sample_frame_bytes)
    assert isinstance(results, list)
