"""Pydantic settings for Commerce Analytics."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    app_env: Literal["development", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "json"

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_consumer_group: str = "commerce_analytics-speed-layer"
    kafka_topic_clickstream: str = "commerce_analytics.clickstream"
    kafka_topic_orders: str = "commerce_analytics.orders"
    kafka_topic_inventory: str = "commerce_analytics.inventory"
    kafka_auto_offset_reset: str = "earliest"
    kafka_enable_auto_commit: bool = False
    schema_registry_url: str = "http://localhost:8081"

    # MySQL
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_db: str = "commerce_analytics_catalog"
    mysql_user: str = "commerce_analytics"
    mysql_password: SecretStr = SecretStr("__PLACEHOLDER__")

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "commerce_analytics_reports"
    postgres_user: str = "commerce_analytics"
    postgres_password: SecretStr = SecretStr("__PLACEHOLDER__")

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    session_timeout_minutes: int = 30

    # AWS
    aws_access_key_id: SecretStr = SecretStr("__PLACEHOLDER__")
    aws_secret_access_key: SecretStr = SecretStr("__PLACEHOLDER__")
    aws_region: str = "us-east-1"
    s3_bucket: str = "commerce_analytics-warehouse"
    s3_raw_prefix: str = "raw/"
    s3_curated_prefix: str = "curated/"

    # Pipeline
    batch_size: int = 1000
    commit_interval_ms: int = 5000
    bot_velocity_threshold: int = 20
    bot_score_block_threshold: float = 0.7

    # Metrics
    prometheus_port: int = 8001

    @property
    def mysql_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:"
            f"{self.mysql_password.get_secret_value()}@"
            f"{self.mysql_host}:{self.mysql_port}/{self.mysql_db}"
        )

    @property
    def postgres_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:"
            f"{self.postgres_password.get_secret_value()}@"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
