"""Tests for Sessionizer."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from commerce_analytics.models import ClickEvent, EventType
from commerce_analytics.streaming import Sessionizer


def make_event(session_id: str, ev: EventType, ts: datetime, product_id: str | None = None) -> ClickEvent:
    return ClickEvent(
        event_id=f"e-{ts.isoformat()}",
        session_id=session_id,
        customer_id="c-1",
        event_type=ev,
        product_id=product_id,
        timestamp=ts,
    )


def test_new_session_created():
    s = Sessionizer()
    ts = datetime.now(tz=timezone.utc)
    sess = s.update(make_event("S1", EventType.PAGE_VIEW, ts))
    assert sess.session_id == "S1"
    assert sess.page_views == 1


def test_page_view_increment():
    s = Sessionizer()
    ts = datetime.now(tz=timezone.utc)
    s.update(make_event("S1", EventType.PAGE_VIEW, ts))
    s.update(make_event("S1", EventType.PAGE_VIEW, ts + timedelta(seconds=10)))
    s.update(make_event("S1", EventType.PAGE_VIEW, ts + timedelta(seconds=20)))
    sess = s.get("S1")
    assert sess.page_views == 3


def test_session_timeout_resets():
    s = Sessionizer()
    ts = datetime.now(tz=timezone.utc)
    s.update(make_event("S1", EventType.PAGE_VIEW, ts))
    later = ts + timedelta(minutes=45)  # > 30 min timeout
    sess = s.update(make_event("S1", EventType.PAGE_VIEW, later))
    # Counts reset since it's a "new" session within the same key
    assert sess.page_views == 1


def test_product_view_tracked():
    s = Sessionizer()
    ts = datetime.now(tz=timezone.utc)
    s.update(make_event("S1", EventType.PRODUCT_VIEW, ts, product_id="P1"))
    s.update(make_event("S1", EventType.PRODUCT_VIEW, ts, product_id="P2"))
    sess = s.get("S1")
    assert "P1" in sess.products_viewed
    assert "P2" in sess.products_viewed
