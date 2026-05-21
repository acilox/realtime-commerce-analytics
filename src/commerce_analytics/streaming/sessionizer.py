"""Real-time sessionization with 30-min inactivity window.

State management:
- Sessions held in-memory (keyed by session_id) for fast updates
- Periodic flush to Redis (HSET) every N events or T seconds
- A session expires when no event has arrived for `timeout_minutes`
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from commerce_analytics.config import get_logger, get_settings
from commerce_analytics.models import ClickEvent, EventType, OrderEvent, Session

logger = get_logger(__name__)


class Sessionizer:
    """In-memory sessionizer with TTL eviction."""

    def __init__(self) -> None:
        s = get_settings()
        self.timeout = timedelta(minutes=s.session_timeout_minutes)
        self._sessions: dict[str, Session] = {}

    def update(self, event: ClickEvent | OrderEvent) -> Session:
        """Update the session with an incoming event. Returns the updated Session."""
        sid = event.session_id
        now = event.timestamp

        if sid in self._sessions:
            sess = self._sessions[sid]
            if now - sess.last_activity > self.timeout:
                # Old session expired — start fresh
                self._sessions[sid] = self._new_session(event)
                sess = self._sessions[sid]
            else:
                sess.last_activity = now
        else:
            sess = self._new_session(event)
            self._sessions[sid] = sess

        self._apply_event(sess, event)
        return sess

    def expire_stale_sessions(self, now: datetime | None = None) -> list[Session]:
        """Return and remove sessions older than timeout. Useful for periodic flush."""
        now = now or datetime.now(tz=timezone.utc)
        cutoff = now - self.timeout
        expired = [
            sid for sid, sess in self._sessions.items() if sess.last_activity < cutoff
        ]
        flushed = [self._sessions.pop(sid) for sid in expired]
        if flushed:
            logger.info("sessions_expired", count=len(flushed))
        return flushed

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def active_count(self) -> int:
        return len(self._sessions)

    # ---- Internal ----
    @staticmethod
    def _new_session(event: ClickEvent | OrderEvent) -> Session:
        return Session(
            session_id=event.session_id,
            customer_id=getattr(event, "customer_id", None),
            start_time=event.timestamp,
            last_activity=event.timestamp,
            user_agent=getattr(event, "user_agent", None),
        )

    @staticmethod
    def _apply_event(sess: Session, event: ClickEvent | OrderEvent) -> None:
        if isinstance(event, ClickEvent):
            sess.customer_id = event.customer_id or sess.customer_id
            if event.event_type == EventType.PAGE_VIEW:
                sess.page_views += 1
            elif event.event_type == EventType.PRODUCT_VIEW and event.product_id:
                sess.products_viewed.append(event.product_id)
                # Cap list size to avoid unbounded growth
                if len(sess.products_viewed) > 100:
                    sess.products_viewed = sess.products_viewed[-100:]
            elif event.event_type == EventType.ADD_TO_CART:
                sess.cart_adds += 1
            elif event.event_type == EventType.CHECKOUT_STARTED:
                sess.checkouts_started += 1
            elif event.event_type == EventType.CHECKOUT_COMPLETED:
                sess.checkouts_completed += 1
        elif isinstance(event, OrderEvent):
            sess.checkouts_completed += 1
            sess.revenue = (sess.revenue or Decimal("0")) + event.total_amount
            sess.customer_id = event.customer_id
