import asyncio

import structlog
from confluent_kafka import Consumer, KafkaError

log = structlog.get_logger()


class Broadcaster:
    """
    Consumes ps.detections from Kafka in a background asyncio task and fans
    each message out to all connected WebSocket clients via per-client queues.
    Queues are bounded (maxsize=50) to drop slow clients rather than grow unbounded.
    """

    def __init__(self, kafka_bootstrap: str, topic: str = "ps.detections") -> None:
        self._bootstrap = kafka_bootstrap
        self._topic = topic
        self._clients: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=50)
        self._clients.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._clients.discard(q)

    async def run(self) -> None:
        loop = asyncio.get_event_loop()
        consumer = Consumer(
            {
                "bootstrap.servers": self._bootstrap,
                "group.id": "pixelstream-dashboard",
                "auto.offset.reset": "latest",
                "enable.auto.commit": True,
            }
        )
        consumer.subscribe([self._topic])
        log.info("broadcaster_started", topic=self._topic, bootstrap=self._bootstrap)
        try:
            while True:
                msg = await loop.run_in_executor(None, lambda: consumer.poll(0.1))
                if msg is None:
                    await asyncio.sleep(0)
                    continue
                if msg.error():
                    if msg.error().code() != KafkaError._PARTITION_EOF:
                        log.error("kafka_error", error=str(msg.error()))
                    continue
                payload = msg.value().decode()
                slow: set[asyncio.Queue] = set()
                for q in list(self._clients):
                    try:
                        q.put_nowait(payload)
                    except asyncio.QueueFull:
                        slow.add(q)
                for q in slow:
                    self._clients.discard(q)
        finally:
            consumer.close()
            log.info("broadcaster_stopped")
