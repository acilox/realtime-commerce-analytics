# realtime-commerce-analytics

A reference implementation of a Lambda-architecture pipeline for
e-commerce clickstream and order data. A Kafka consumer handles
sessionisation and bot scoring with sub-second latency; a nightly
Airflow batch recomputes CLV and funnel rollups against the same source
events.

## Problem domain

E-commerce platforms need both real-time decisions (live session
counters, inventory state, bot rejection) and batch analytics (CLV
modelling, cohort retention, conversion funnels) over the same event
stream. The patterns here split a single source-of-truth event log
between a streaming speed layer and a nightly batch layer, with
deterministic merge semantics on the serving side.

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
inactivity. A periodic flush task pushes them into Redis as `HSET`
records under `commerce_analytics:session:<id>` with a 24-hour TTL so
dashboards retain them after the session ends.

State currently lives on the consumer process. For multi-instance
deployments, swap the in-memory dict for a Redis hash keyed the same
way — the rest of the code is unchanged.

## Bot scoring

Heuristic, not ML. User-agent matches against a hardcoded substring
list (catches `python-requests`, headless browsers, common scrapers),
combined with event velocity and missing-referrer signals. Suitable for
deflecting obvious automation at the API gateway; subtler patterns
should flow to a downstream fraud-review system.

## CLV

`CLVCalculator.compute()` uses `lifetimes` (BG/NBD + Gamma-Gamma) when
the package is installed, and falls back to a `(frequency / tenure_days)
* 365 * avg_value` heuristic otherwise, so CI runs without the
optional dependency.

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

## Design notes

- Topics are partitioned by `session_id` (clickstream) and `order_id`
  (orders). The consumer group's partition assignment matches, so
  sessions do not fragment across workers.
- Offsets are committed manually after a successful handler — no
  auto-commit. This gives at-least-once semantics; idempotency on the
  target side (Redis HSET overwrites) absorbs duplicates.
- Schema Registry is configured in docker-compose but the consumer
  reads plain JSON. Migrating to Avro or Protobuf is a one-day change
  isolated to the deserialisation layer.

## About this code

Open-source companion to the streaming and analytics work done by
[acilox](https://github.com/acilox). For paid implementation,
hardening, or extension of these patterns — including production
schema-registry integration and HA consumer deployments — open an
issue.
