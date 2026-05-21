"""Purchase funnel analyzer."""

from __future__ import annotations

import pandas as pd

from commerce_analytics.config import get_logger
from commerce_analytics.models import EventType

logger = get_logger(__name__)


DEFAULT_FUNNEL = [
    EventType.PAGE_VIEW,
    EventType.PRODUCT_VIEW,
    EventType.ADD_TO_CART,
    EventType.CHECKOUT_STARTED,
    EventType.CHECKOUT_COMPLETED,
]


class FunnelAnalyzer:
    """Computes conversion rates between funnel stages."""

    def __init__(self, stages: list[EventType] | None = None) -> None:
        self.stages = stages or DEFAULT_FUNNEL

    def analyze(self, events_df: pd.DataFrame) -> pd.DataFrame:
        """Compute count + conversion rate for each stage.

        Required columns: session_id, event_type, timestamp.
        """
        if events_df.empty:
            return pd.DataFrame(columns=["stage", "sessions", "conversion_pct"])

        rows = []
        prior = None
        for stage in self.stages:
            mask = events_df["event_type"] == stage.value
            sessions = events_df.loc[mask, "session_id"].nunique()
            conversion = 100.0 if prior is None or prior == 0 else (sessions / prior) * 100.0
            rows.append({"stage": stage.value, "sessions": sessions, "conversion_pct": conversion})
            prior = sessions

        result = pd.DataFrame(rows)
        logger.info("funnel_computed", stages=len(result))
        return result
