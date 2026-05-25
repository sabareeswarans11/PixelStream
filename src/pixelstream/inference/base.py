from abc import ABC, abstractmethod

from pixelstream.schemas import Detection


class InferenceBackend(ABC):
    @property
    def model_name(self) -> str:
        return self.__class__.__name__.lower()

    @abstractmethod
    def detect(self, frame_bytes: bytes) -> list[Detection]:
        """Run inference on a JPEG frame and return detections."""
        ...

    def switch_model(self, model_name: str) -> None:
        raise NotImplementedError(f"{self.__class__.__name__} does not support model switching")
