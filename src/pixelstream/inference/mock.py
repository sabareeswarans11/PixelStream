import random

from pixelstream.inference.base import InferenceBackend
from pixelstream.schemas import Detection

_CLASSES = ["person", "car", "bicycle", "truck", "dog", "cat"]


class MockBackend(InferenceBackend):
    """Returns random bounding boxes with no real inference. For unit tests and dev."""

    @property
    def model_name(self) -> str:
        return "mock"

    def detect(self, frame_bytes: bytes) -> list[Detection]:
        n = random.randint(1, 3)
        detections = []
        for _ in range(n):
            x1 = round(random.uniform(0.0, 0.45), 3)
            y1 = round(random.uniform(0.0, 0.45), 3)
            detections.append(
                Detection(
                    cls=random.choice(_CLASSES),
                    confidence=round(random.uniform(0.50, 0.99), 3),
                    bbox=[
                        x1,
                        y1,
                        round(x1 + random.uniform(0.1, 0.5), 3),
                        round(y1 + random.uniform(0.1, 0.5), 3),
                    ],
                )
            )
        return detections
