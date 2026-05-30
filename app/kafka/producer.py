"""
Kafka Producer for FlashLedger

Publishes trade and order events to Kafka topics.
Gracefully degrades if Kafka is not available.
"""
import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from confluent_kafka import Producer as ConfluentProducer
    _CONFLUENT_AVAILABLE = True
except ImportError:
    _CONFLUENT_AVAILABLE = False
    logger.warning("confluent-kafka not installed — Kafka publishing disabled")

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")

_producer: Optional[object] = None


def _delivery_callback(err, msg):
    if err:
        logger.error("Kafka delivery failed [%s]: %s", msg.topic(), err)


def get_producer():
    global _producer
    if not _CONFLUENT_AVAILABLE:
        return None
    if _producer is None:
        try:
            _producer = ConfluentProducer({
                "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
                "client.id": "flashledger-producer",
                "acks": "all",
                "retries": 3,
                "retry.backoff.ms": 100,
                "socket.timeout.ms": 3000,
                "message.timeout.ms": 5000,
            })
            logger.info("Kafka producer connected to %s", KAFKA_BOOTSTRAP_SERVERS)
        except Exception as exc:
            logger.warning("Kafka producer init failed: %s", exc)
            _producer = None
    return _producer


def publish(topic: str, payload: dict) -> None:
    """Publish a JSON message to a Kafka topic (fire-and-forget, non-blocking)."""
    producer = get_producer()
    if producer is None:
        return
    try:
        key = (payload.get("trade_id") or payload.get("order_id") or "").encode("utf-8")
        producer.produce(
            topic=topic,
            value=json.dumps(payload).encode("utf-8"),
            key=key,
            callback=_delivery_callback,
        )
        producer.poll(0)  # trigger delivery callbacks without blocking
    except Exception as exc:
        logger.error("Kafka publish to '%s' failed: %s", topic, exc)


def flush(timeout: float = 5.0) -> None:
    """Flush pending messages on graceful shutdown."""
    producer = get_producer()
    if producer:
        producer.flush(timeout=timeout)
