"""Tests for BotDetector."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from commerce_analytics.models import ClickEvent, EventType, Session
from commerce_analytics.streaming import BotDetector


def evt(
    session_id: str, ua: str | None, ts: datetime, referrer: str | None = "https://google.com"
) -> ClickEvent:
    return ClickEvent(
        event_id=f"e-{ts.timestamp()}",
        session_id=session_id,
        customer_id=None,
        event_type=EventType.PAGE_VIEW,
        user_agent=ua,
        referrer=referrer,
        timestamp=ts,
    )


def sess(session_id: str) -> Session:
    now = datetime.now(tz=UTC)
    return Session(session_id=session_id, start_time=now, last_activity=now)


def test_human_low_score():
    d = BotDetector()
    ts = datetime.now(tz=UTC)
    s = sess("HUM")
    score = d.update(evt("HUM", "Mozilla/5.0 Chrome", ts), s)
    assert score < 0.5


def test_bot_ua_max_score():
    d = BotDetector()
    ts = datetime.now(tz=UTC)
    s = sess("BOT")
    score = d.update(evt("BOT", "python-requests/2.31", ts), s)
    assert score == 1.0


def test_velocity_triggers():
    d = BotDetector()
    ts = datetime.now(tz=UTC)
    s = sess("VEL")
    score = 0.0
    for i in range(30):
        score = d.update(evt("VEL", "Mozilla/5.0", ts + timedelta(seconds=i)), s)
    assert score >= 0.5
