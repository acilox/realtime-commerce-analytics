"""S3 Parquet writer for raw + curated zones."""

from __future__ import annotations

from datetime import date
from io import BytesIO

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from commerce_analytics.config import get_logger, get_settings

logger = get_logger(__name__)


class S3ParquetWriter:
    """Writes DataFrames to S3 with Hive-partitioned date paths."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._s3 = None

    def __enter__(self):
        self._connect()
        return self

    def __exit__(self, *_):
        pass

    def _connect(self) -> None:
        import boto3  # type: ignore[import-not-found]

        self._s3 = boto3.client(
            "s3",
            aws_access_key_id=self.settings.aws_access_key_id.get_secret_value(),
            aws_secret_access_key=self.settings.aws_secret_access_key.get_secret_value(),
            region_name=self.settings.aws_region,
        )

    def write(self, df: pd.DataFrame, table: str, partition_date: date, zone: str = "raw") -> int:
        if self._s3 is None:
            self._connect()
        assert self._s3 is not None

        if df.empty:
            return 0

        prefix = self.settings.s3_raw_prefix if zone == "raw" else self.settings.s3_curated_prefix
        key = (
            f"{prefix}{table}/year={partition_date.year:04d}/"
            f"month={partition_date.month:02d}/day={partition_date.day:02d}/"
            f"part-{partition_date.strftime('%Y%m%d')}.parquet"
        )

        sink = BytesIO()
        pq.write_table(pa.Table.from_pandas(df), sink, compression="snappy")
        self._s3.put_object(
            Bucket=self.settings.s3_bucket,
            Key=key,
            Body=sink.getvalue(),
            Metadata={"record_count": str(len(df))},
        )
        logger.info("s3_written", table=table, key=key, rows=len(df))
        return len(df)
