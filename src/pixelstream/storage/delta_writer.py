import structlog
from pyspark.sql import SparkSession
from pyspark.sql.types import (
    ArrayType,
    DoubleType,
    FloatType,
    StringType,
    StructField,
    StructType,
)

from pixelstream.schemas import DetectionResult

log = structlog.get_logger()

_DETECTION_SCHEMA = StructType(
    [
        StructField("cls", StringType(), True),
        StructField("confidence", FloatType(), True),
        StructField("bbox", ArrayType(FloatType()), True),
    ]
)

_RESULT_SCHEMA = StructType(
    [
        StructField("frame_id", StringType(), False),
        StructField("timestamp", DoubleType(), False),
        StructField("model", StringType(), False),
        StructField("latency_ms", FloatType(), False),
        StructField("detections", ArrayType(_DETECTION_SCHEMA), True),
    ]
)


class DeltaWriter:
    def __init__(self, path: str, spark: SparkSession) -> None:
        self._path = path
        self._spark = spark

    def write(self, results: list[DetectionResult]) -> None:
        rows = [_to_row(r) for r in results]
        df = self._spark.createDataFrame(rows, schema=_RESULT_SCHEMA)
        df.write.format("delta").mode("append").save(self._path)
        log.info("delta_written", rows=len(rows), path=self._path)

    def read_recent(self, limit: int = 200) -> list[dict]:
        try:
            df = self._spark.read.format("delta").load(self._path)
            rows = df.orderBy("timestamp", ascending=False).limit(limit).collect()
            return [row.asDict(recursive=True) for row in rows]
        except Exception:
            return []


def _to_row(r: DetectionResult) -> dict:
    return {
        "frame_id": r.frame_id,
        "timestamp": r.timestamp,
        "model": r.model,
        "latency_ms": float(r.latency_ms),
        "detections": [
            {"cls": d.cls, "confidence": float(d.confidence), "bbox": [float(v) for v in d.bbox]}
            for d in r.detections
        ],
    }
