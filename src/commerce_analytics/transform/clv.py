"""Customer Lifetime Value calculator.

Uses the lifetimes library to fit a BG/NBD model on RFM-style features.
Falls back to a simple heuristic if `lifetimes` isn't installed.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pandas as pd

from commerce_analytics.config import get_logger

logger = get_logger(__name__)


class CLVCalculator:
    """Compute predicted CLV per customer from order history."""

    def __init__(self, prediction_horizon_days: int = 365) -> None:
        self.prediction_horizon_days = prediction_horizon_days

    def compute(self, orders_df: pd.DataFrame) -> pd.DataFrame:
        """Compute CLV from orders DataFrame.

        Required columns: customer_id, order_id, order_timestamp, order_total.
        """
        if orders_df.empty:
            return pd.DataFrame(columns=["customer_id", "predicted_clv"])

        # Use lifetimes BG/NBD if available, else simple frequency*value heuristic
        try:
            from lifetimes import BetaGeoFitter, GammaGammaFitter  # type: ignore[import-not-found]
            from lifetimes.utils import summary_data_from_transaction_data  # type: ignore[import-not-found]

            return self._fit_bgnbd(orders_df, BetaGeoFitter, GammaGammaFitter, summary_data_from_transaction_data)
        except ImportError:
            logger.warning("lifetimes_not_installed_using_heuristic")
            return self._heuristic_clv(orders_df)

    def _fit_bgnbd(self, df, BGNBD, GammaGamma, summary_fn) -> pd.DataFrame:
        df = df.copy()
        df["order_timestamp"] = pd.to_datetime(df["order_timestamp"])
        summary = summary_fn(
            df,
            customer_id_col="customer_id",
            datetime_col="order_timestamp",
            monetary_value_col="order_total",
            observation_period_end=df["order_timestamp"].max(),
        )

        bgf = BGNBD(penalizer_coef=0.0)
        bgf.fit(summary["frequency"], summary["recency"], summary["T"])

        ggf = GammaGamma(penalizer_coef=0.0)
        # GammaGamma requires repeat customers (frequency >= 1)
        returning = summary[summary["frequency"] > 0]
        if returning.empty:
            return self._heuristic_clv(df)
        ggf.fit(returning["frequency"], returning["monetary_value"])

        clv = ggf.customer_lifetime_value(
            bgf,
            summary["frequency"],
            summary["recency"],
            summary["T"],
            summary["monetary_value"],
            time=self.prediction_horizon_days // 30,  # in months
            discount_rate=0.01,
        )
        result = pd.DataFrame({"customer_id": summary.index, "predicted_clv": clv.values})
        logger.info("clv_computed", customer_count=len(result))
        return result

    def _heuristic_clv(self, df: pd.DataFrame) -> pd.DataFrame:
        agg = (
            df.groupby("customer_id")
            .agg(
                frequency=("order_id", "count"),
                avg_value=("order_total", "mean"),
                first_order=("order_timestamp", "min"),
                last_order=("order_timestamp", "max"),
            )
            .reset_index()
        )
        agg["first_order"] = pd.to_datetime(agg["first_order"])
        agg["last_order"] = pd.to_datetime(agg["last_order"])
        tenure_days = (agg["last_order"] - agg["first_order"]).dt.days.clip(lower=1)
        # Annualized: (freq / tenure_days) * 365 * avg_value
        agg["predicted_clv"] = (agg["frequency"] / tenure_days) * 365 * agg["avg_value"]
        return agg[["customer_id", "predicted_clv"]]
