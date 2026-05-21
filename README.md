# realtime-commerce-analytics

Lambda-architecture pipeline for e-commerce clickstream and order data. A
Kafka consumer handles sessionisation and bot scoring with sub-second
latency; a nightly Airflow batch recomputes CLV and the conversion funnel.

## Problem

Marketing wanted real-time session counters for the homepage dashboard
and the data science team wanted CLV recomputed every night, both on top
of the same Kafka topics. Rather than maintain two divergent code paths
we built one library with two entry points: a streaming consumer and a
batch DAG.

## Topology

```
                kafka topics                 stores
                ------------                 ------
                clickstream  --+
   producers -->              +-> speed   -> redis (live sessions)
                orders       --+   layer  -> redis (RT dashboard hsets)
                inventory    --+
                                +-> batch  -> postgres (reports)
                                    layer  -> s3 (parquet, curated)
mysql (catalog) -----------------> batch -> s3 (raw zone)
```

## Layout

```
src/commerce_analytics/
  config/        settings + logging
  models/        ClickEvent, OrderEvent, InventoryEvent, Session
  streaming/     KafkaConsumerService, Sessionizer, BotDetector
  transform/     CLVCalculator (BG/NBD via lifetimes), FunnelAnalyzer
  extract/       MySQLCatalogExtractor (batch layer only)
  load/          RedisSessionWriter, S3ParquetWriter
  orchestration/ Airflow DAG for the batch side
  main.py        Typer CLI (demo, consume, produce-sample, batch)
```

## Sessionisation

In-memory sessions keyed by `session_id`, evicted after 30 minutes of
inactivity. A periodic flush task pushes them into Redis as `HSET`s
under `commerce_analytics:session:<id>` with a 24h TTL so dashboards
keep them visible after the session ends.

State currently lives on the consumer. If you ever need to scale the
speed layer past one instance, swap the in-memory dict for a Redis hash
keyed the same way — the rest of the code shouldn't have to change.

## Bot scoring

Cheap heuristics, not ML. UA-matches against a hardcoded substring list
(catches `python-requests`, headless browsers, common scrapers), plus
event velocity and missing-referrer signals. Good enough to deflect the
obvious junk at the API gateway; anything subtle goes through fraud
review downstream.

## CLV

`CLVCalculator.compute()` uses `lifetimes` (BG/NBD + Gamma-Gamma) when
the package is installed, and falls back to a heuristic
`(frequency / tenure_days) * 365 * avg_value` otherwise so the CI tests
don't need the dependency.

## Running locally

```
cp .env.example .env
make install
make docker-up                # kafka, mysql, postgres, redis
make demo                     # runs against data/sample/ — no kafka needed
make produce-sample           # push 100 events into the kafka topic
make consume                  # speed layer (Ctrl-C to stop)
make run-batch                # nightly batch logic, one-shot
```

## Stack

Python 3.11, confluent-kafka, polars, pandas, lifetimes, pymysql,
psycopg2, redis, pyarrow, structlog, pydantic, Airflow 2.x.

## Notes

- Topics are partitioned by `session_id` (clickstream) and `order_id`
  (orders). The consumer group has matching partition assignment so
  sessions don't fragment across workers.
- Offsets are committed manually after a successful handler — no
  auto-commit. That gives us at-least-once; idempotency on the target
  side (Redis HSET overwrites) handles duplicates.
- Schema Registry is configured in compose but the consumer reads
  plain JSON for now. Avro / Protobuf swap is a one-day job.
