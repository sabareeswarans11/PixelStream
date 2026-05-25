from pydantic import BaseModel, field_validator


class FrameMessage(BaseModel):
    frame_id: str
    timestamp: float
    source_id: str
    frame_b64: str  # JPEG base64-encoded
    width: int
    height: int


class Detection(BaseModel):
    cls: str
    confidence: float
    bbox: list[float]  # [x1, y1, x2, y2] normalized to [0, 1]

    @field_validator("confidence")
    @classmethod
    def confidence_in_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"confidence must be in [0, 1], got {v}")
        return v

    @field_validator("bbox")
    @classmethod
    def bbox_four_elements(cls, v: list[float]) -> list[float]:
        if len(v) != 4:
            raise ValueError(f"bbox must have 4 elements [x1,y1,x2,y2], got {len(v)}")
        return v


class DetectionResult(BaseModel):
    frame_id: str
    timestamp: float
    model: str
    latency_ms: float
    detections: list[Detection]
