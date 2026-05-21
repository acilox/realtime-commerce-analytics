"""Redis writer for sessions + real-time dashboards."""

from __future__ import annotations

import json
from typing import Iterable

from commerce_analytics.config import get_logger, get_settings
from commerce_analytics.models import Session

logger = get_logger(__name__)


class RedisSessionWriter:
    """Persists Session objects to Redis (HSET per session)."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = None

    def __enter__(self):
        self._connect()
        return self

    def __exit__(self, *_):
        if self._client is not None:
            self._client.close()

    def _connect(self) -> None:
        import redis  # type: ignore[import-not-found]

        s = self.settings
        self._client = redis.Redis(
            host=s.redis_host,
            port=s.redis_port,
            db=s.redis_db,
            decode_responses=True,
        )
        self._client.ping()
        logger.info("redis_connected")

    def flush(self, sessions: Iterable[Session]) -> int:
        if self._client is None:
            self._connect()
        assert self._client is not None
        count = 0
        pipe = self._client.pipeline()
        for sess in sessions:
            key = f"commerce_analytics:session:{sess.session_id}"
            mapping = {
                "customer_id": sess.customer_id or "",
                "start_time": sess.start_time.isoformat(),
                "last_activity": sess.last_activity.isoformat(),
                "page_views": sess.page_views,
                "cart_adds": sess.cart_adds,
                "checkouts_started": sess.checkouts_started,
                "checkouts_completed": sess.checkouts_completed,
                "revenue": str(sess.revenue),
                "bot_score": sess.bot_score,
                "products_viewed": json.dumps(sess.products_viewed),
            }
            pipe.hset(key, mapping=mapping)
            pipe.expire(key, 60 * 60 * 24)  # 24h TTL
            count += 1
        pipe.execute()
        logger.info("redis_sessions_flushed", count=count)
        return count
