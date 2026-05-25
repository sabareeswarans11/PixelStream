import base64
import io

import numpy as np
from PIL import Image

from pixelstream.producer.frame_producer import encode_frame


def make_frame(h: int = 480, w: int = 640) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=np.uint8)


def test_encode_frame_returns_bytes():
    frame = make_frame()
    result = encode_frame(frame)
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_encode_frame_size_under_50kb():
    """Each Kafka message must be < 50KB to keep throughput healthy."""
    frame = make_frame()
    result = encode_frame(frame)
    assert len(result) < 50_000, f"Frame too large: {len(result)} bytes"


def test_encode_frame_is_valid_jpeg():
    frame = make_frame()
    jpg = encode_frame(frame)
    img = Image.open(io.BytesIO(jpg))
    assert img.format == "JPEG"


def test_encode_frame_resizes_to_640x480():
    # Start with a different size
    frame = make_frame(h=1080, w=1920)
    jpg = encode_frame(frame)
    img = Image.open(io.BytesIO(jpg))
    assert img.size == (640, 480)


def test_frame_b64_roundtrip():
    frame = make_frame()
    jpg_bytes = encode_frame(frame)
    b64 = base64.b64encode(jpg_bytes).decode()
    recovered = base64.b64decode(b64)
    assert recovered == jpg_bytes
