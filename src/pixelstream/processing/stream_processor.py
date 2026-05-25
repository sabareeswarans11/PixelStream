import structlog
from pyspark.sql import SparkSession

from pixelstream.config import settings
from pixelstream.inference.ultralytics_backend import UltralyticsBackend
from pixelstream.processing.batch_handler import BatchHandler
from pixelstream.storage.delta_writer import DeltaWriter

log = structlog.get_logger()

_KAFKA_JARS = "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,io.delta:delta-spark_2.12:3.2.0"


def create_spark() -> SparkSession:
    return (
        SparkSession.builder.appName("PixelStream")
        .master("local[*]")
        .config("spark.jars.packages", _KAFKA_JARS)
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
    )


def main() -> None:
    spark = create_spark()
    spark.sparkContext.setLogLevel("ERROR")

    backend = UltralyticsBackend(settings.default_model)
    writer = DeltaWriter(settings.delta_path, spark)
    handler = BatchHandler(backend, writer)

    stream = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", settings.kafka_bootstrap)
        .option("subscribe", "ps.frames")
        .option("startingOffsets", "latest")
        .option("failOnDataLoss", "false")
        .load()
    )

    query = (
        stream.writeStream.foreachBatch(handler.handle)
        .trigger(processingTime="5 seconds")
        .option("checkpointLocation", "data/checkpoints/spark")
        .start()
    )

    log.info("streaming_started", kafka=settings.kafka_bootstrap, model=settings.default_model)
    query.awaitTermination()


if __name__ == "__main__":
    main()
