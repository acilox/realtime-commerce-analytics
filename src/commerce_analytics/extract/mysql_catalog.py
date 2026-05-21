"""MySQL product catalog extractor."""

from __future__ import annotations

import pandas as pd
from sqlalchemy import create_engine, text

from commerce_analytics.config import get_logger, get_settings

logger = get_logger(__name__)


PRODUCT_QUERY = """
SELECT product_id, sku, name, category, brand, price, currency, in_stock, updated_at
FROM products
"""


class MySQLCatalogExtractor:
    """Snapshot extract of the product catalog."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.engine = None

    def __enter__(self):
        self.engine = create_engine(self.settings.mysql_url, pool_pre_ping=True)
        return self

    def __exit__(self, *_):
        if self.engine is not None:
            self.engine.dispose()

    def extract(self) -> pd.DataFrame:
        assert self.engine is not None
        df = pd.read_sql(text(PRODUCT_QUERY), self.engine)
        logger.info("catalog_extracted", rows=len(df))
        return df
