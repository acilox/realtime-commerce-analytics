"""Heuristic bot/automation detector for clickstream events."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta

from commerce_analytics.config import get_logger, get_settings
from commerce_analytics.models import ClickEvent, Session

logger = get_logger(__name__)


# Well-known bot UA substrings
BOT_UA_HINTS = (
    "bot",
    "crawler",
    "spider",
    "scraper",
    "curl",
    "wget",
    "python-requests",
    "httpclient",
    "headless",
)


class BotDetector:
    """Compute a bot probability score [0, 1] per session.

    Rules:
    - >N page views in <30s → score += 0.5
    - UA matches BOT_UA_HINTS → score = 1.0
    - Missing referrer + missing user-agent → score += 0.3
    - >50 product views in one session → score += 0.2
    """

    def __init__(self) -> None:
        s = get_settings()
        self.velocity_threshold = s.bot_velocity_threshold

        self._velocity_window: dict[str, deque[datetime]] = {}

    def update(self, event: ClickEvent, session: Session) -> float:
        score = 0.0
        signals: list[str] = []

        # UA check
        if event.user_agent:
            ua = event.user_agent.lower()
            if any(h in ua for h in BOT_UA_HINTS):
                signals.append("ua_match")
                session.bot_score = 1.0
                return 1.0
        else:
            score += 0.2
            signals.append("missing_ua")

        # Velocity check
        window = self._velocity_window.setdefault(event.session_id, deque(maxlen=200))
        window.append(event.timestamp)
        cutoff = event.timestamp - timedelta(seconds=30)
        in_window = sum(1 for ts in window if ts >= cutoff)
        if in_window > self.velocity_threshold:
            score += 0.5
            signals.append("velocity")

        # Product overload
        if len(session.products_viewed) > 50:
            score += 0.2
            signals.append("product_overload")

        # Missing referrer
        if not event.referrer:
            score += 0.1
            signals.append("missing_referrer")

        score = min(1.0, score)
        session.bot_score = max(session.bot_score, score)

        if score >= 0.7:
            logger.warning(
                "bot_suspected",
                session_id=event.session_id,
                score=session.bot_score,
                signals=signals,
            )
        return session.bot_score
