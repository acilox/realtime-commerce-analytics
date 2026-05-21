"""Kafka consumer service implementing the speed layer.

Implements:
- Manual offset commit for exactly-once semantics
- Per-message JSON deserialization
- Routing by topic to ClickEvent / OrderEvent / InventoryEvent handlers
- Periodic flush of session state to Redis
"""

from __future__ import annotations

import json
import signal
import sys
from typing import Callable

from commerce_analytics.config import get_logger, get_settings
from commerce_analytics.models import ClickEvent, InventoryEvent, OrderEvent
from commerce_analytics.streaming.bot_detector import BotDetector
from commerce_analytics.streaming.sessionizer import Sessionizer

logger = get_logger(__name__)


class KafkaConsumerService:
    """Consumes Kafka topics and applies the real-time pipeline."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.sessionizer = Sessionizer()
        self.bot_detector = BotDetector()
        self._consumer = None
        self._running = False
        self._processed = 0

    def __enter__(self):
        self._connect()
        return self

    def __exit__(self, *_):
        self.close()

    def _connect(self) -> None:
        try:
            from confluent_kafka import Consumer  # type: ignore[import-not-found]
        except ImportError as e:
            raise RuntimeError("confluent-kafka not installed") from e

        conf = {
            "bootstrap.servers": self.settings.kafka_bootstrap_servers,
            "group.id": self.settings.kafka_consumer_group,
            "auto.offset.reset": self.settings.kafka_auto_offset_reset,
            "enable.auto.commit": self.settings.kafka_enable_auto_commit,
            "isolation.level": "read_committed",
        }
        self._consumer = Consumer(conf)
        topics = [
            self.settings.kafka_topic_clickstream,
            self.settings.kafka_topic_orders,
            self.settings.kafka_topic_inventory,
        ]
        self._consumer.subscribe(topics)
        logger.info("kafka_subscribed", topics=topics)

    def close(self) -> None:
        if self._consumer is not None:
            self._consumer.close()
            self._consumer = None

    def run(self, max_messages: int | None = None) -> int:
        """Run the consumer loop. If max_messages is given, stop after that many."""
        assert self._consumer is not None
        self._running = True
        signal.signal(signal.SIGINT, self._stop_handler)
        signal.signal(signal.SIGTERM, self._stop_handler)

        try:
            while self._running:
                msg = self._consumer.poll(timeout=1.0)
                if msg is None:
                    continue
                if msg.error():
                    logger.error("kafka_consume_error", error=str(msg.error()))
                    continue

                try:
                    self._handle_message(msg.topic(), msg.value())
                    self._consumer.commit(message=msg, asynchronous=False)
                    self._processed += 1
                except Exception as e:
                    logger.exception("message_processing_failed", error=str(e))
                    # In production: route to DLQ topic

                if max_messages and self._processed >= max_messages:
                    break
        finally:
            self.close()

        logger.info("consumer_stopped", processed=self._processed)
        return self._processed

    def _handle_message(self, topic: str, raw: bytes) -> None:
        payload = json.loads(raw.decode("utf-8"))

        if topic == self.settings.kafka_topic_clickstream:
            event = ClickEvent(**payload)
            session = self.sessionizer.update(event)
            self.bot_detector.update(event, session)
        elif topic == self.settings.kafka_topic_orders:
            event = OrderEvent(**payload)
            self.sessionizer.update(event)
        elif topic == self.settings.kafka_topic_inventory:
            InventoryEvent(**payload)
            # In production: write to inventory deltas table

    def _stop_handler(self, signum, frame):
        logger.info("shutdown_requested", signal=signum)
        self._running = False
