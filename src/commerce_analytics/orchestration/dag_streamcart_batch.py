"""Airflow batch DAG for Commerce Analytics — nightly enrichment & analytics."""

from __future__ import annotations

from datetime import datetime, timedelta

try:
    from airflow import DAG  # type: ignore[import-not-found]
    from airflow.operators.python import PythonOperator  # type: ignore[import-not-found]

    AIRFLOW_AVAILABLE = True
except ImportError:
    AIRFLOW_AVAILABLE = False


DEFAULT_ARGS = {
    "owner": "commerce_analytics",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
}


def _run_clv(**context):
    import pandas as pd

    from commerce_analytics.transform import CLVCalculator

    # In real impl: read orders from S3 raw zone
    df = pd.DataFrame()
    CLVCalculator().compute(df)


def _run_funnels(**context):
    import pandas as pd

    from commerce_analytics.transform import FunnelAnalyzer

    df = pd.DataFrame()
    FunnelAnalyzer().analyze(df)


if AIRFLOW_AVAILABLE:
    with DAG(
        dag_id="commerce_analytics_batch",
        default_args=DEFAULT_ARGS,
        schedule="0 3 * * *",  # 03:00 UTC daily
        start_date=datetime(2026, 1, 1),
        catchup=False,
        tags=["commerce_analytics", "etl", "ecommerce"],
    ) as dag:
        clv = PythonOperator(task_id="compute_clv", python_callable=_run_clv)
        funnel = PythonOperator(task_id="compute_funnels", python_callable=_run_funnels)
        clv >> funnel
