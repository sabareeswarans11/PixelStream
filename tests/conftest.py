import io

import numpy as np
import pytest
from PIL import Image


@pytest.fixture(scope="session")
def sample_frame_bytes() -> bytes:
    """240×320 JPEG bytes — synthetic frame for inference tests."""
    arr = np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8)
    img = Image.fromarray(arr, "RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()


@pytest.fixture
def mock_backend():
    from pixelstream.inference.mock import MockBackend

    return MockBackend()


@pytest.fixture(scope="session")
def spark():
    """Minimal SparkSession for unit tests — no Kafka jars, no Delta."""
    from pyspark.sql import SparkSession

    s = (
        SparkSession.builder.appName("pixelstream-test")
        .master("local[1]")
        .config("spark.sql.shuffle.partitions", "1")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    s.sparkContext.setLogLevel("ERROR")
    yield s
    s.stop()
