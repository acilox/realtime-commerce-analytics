# Commerce Analytics Architecture

## Lambda Architecture

```mermaid
flowchart LR
    subgraph Sources
        K[Kafka<br/>events]
        DB[(MySQL<br/>catalog)]
    end

    subgraph Speed["Speed Layer (Kafka consumers)"]
        S1[Sessionizer]
        S2[Bot Detector]
        S3[Inventory deltas]
    end

    subgraph Batch["Batch Layer (Airflow)"]
        B1[Funnel Analysis]
        B2[CLV Calculator]
        B3[Recommender Features]
    end

    subgraph Serving
        RD[(Redis<br/>RT dashboards)]
        PG[(PostgreSQL<br/>Reports)]
        S3S[(S3 Parquet)]
    end

    K --> S1 --> RD
    K --> S2 --> RD
    K --> S3 --> RD
    K --> B1 --> PG
    K --> B2 --> PG
    DB --> B1
    DB --> B3 --> S3S
```

## Exactly-Once Guarantees

| Source | Mechanism |
|--------|-----------|
| Kafka  | `isolation.level=read_committed` + manual offset commit |
| Sinks  | Idempotent keys (`session_id`, `customer_id`) + upserts |
| State  | Sessionizer flushes via Redis pipeline with WATCH/MULTI |

## Latency Targets

- Speed layer: < 500ms p95
- Batch layer: < 30 min for daily windows
- Dashboard refresh: < 5s (Redis HSET reads)
