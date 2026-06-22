"""Commerce Analytics CLI."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import typer
from rich.console import Console
from rich.table import Table

from commerce_analytics.config import configure_logging, get_logger, get_settings
from commerce_analytics.models import ClickEvent, EventType
from commerce_analytics.streaming import BotDetector, Sessionizer
from commerce_analytics.transform import CLVCalculator, FunnelAnalyzer

app = typer.Typer(name="commerce_analytics", help="Commerce Analytics CLI", no_args_is_help=True)
console = Console()
logger = get_logger(__name__)


def _bootstrap() -> None:
    s = get_settings()
    configure_logging(s.log_level, s.log_format)


@app.command()
def demo() -> None:
    """Run the demo pipeline against sample CSV events (no Kafka required)."""
    _bootstrap()
    pkg_dir = Path(__file__).resolve().parent.parent.parent
    events_path = pkg_dir / "data" / "sample" / "events.csv"
    orders_path = pkg_dir / "data" / "sample" / "orders.csv"

    if not events_path.exists():
        events_path = Path("data/sample/events.csv")
        orders_path = Path("data/sample/orders.csv")

    events_df = pd.read_csv(events_path, parse_dates=["timestamp"])
    orders_df = pd.read_csv(orders_path, parse_dates=["order_timestamp"])

    sessionizer = Sessionizer()
    bot_detector = BotDetector()

    for _, row in events_df.iterrows():
        evt = ClickEvent(
            event_id=row["event_id"],
            session_id=row["session_id"],
            customer_id=row.get("customer_id"),
            event_type=EventType(row["event_type"]),
            product_id=row.get("product_id"),
            page_url=row.get("page_url"),
            referrer=row.get("referrer"),
            user_agent=row.get("user_agent"),
            ip_address=row.get("ip_address"),
            timestamp=row["timestamp"].to_pydatetime(),
        )
        sess = sessionizer.update(evt)
        bot_detector.update(evt, sess)

    # Summary
    table = Table(title=f"Commerce Analytics Demo — {sessionizer.active_count()} sessions")
    table.add_column("session_id", style="cyan")
    table.add_column("page_views", justify="right")
    table.add_column("cart_adds", justify="right")
    table.add_column("checkouts_completed", justify="right")
    table.add_column("revenue", justify="right", style="green")
    table.add_column("bot_score", justify="right", style="red")
    for sid, sess in list(sessionizer._sessions.items())[:15]:
        table.add_row(
            sid,
            str(sess.page_views),
            str(sess.cart_adds),
            str(sess.checkouts_completed),
            f"${sess.revenue}",
            f"{sess.bot_score:.2f}",
        )
    console.print(table)

    # Funnel
    fun = FunnelAnalyzer().analyze(events_df)
    console.print("\n[bold]Conversion Funnel:[/]")
    for _, row in fun.iterrows():
        console.print(
            f"  {row['stage']:<25} sessions={row['sessions']:>4}   "
            f"conv={row['conversion_pct']:.1f}%"
        )

    # CLV (heuristic on sample orders)
    if not orders_df.empty:
        clv_df = CLVCalculator().compute(orders_df)
        console.print("\n[bold]Top CLV customers:[/]")
        for _, row in clv_df.head(5).iterrows():
            console.print(f"  {row['customer_id']:<15} CLV=${row['predicted_clv']:.2f}")


@app.command()
def consume(max_messages: int = typer.Option(0, help="Stop after N msgs (0=forever)")) -> None:
    """Run the speed-layer Kafka consumer."""
    _bootstrap()
    from commerce_analytics.streaming import KafkaConsumerService

    with KafkaConsumerService() as svc:
        svc.run(max_messages=max_messages or None)


@app.command(name="produce-sample")
def produce_sample(count: int = typer.Option(100, help="Number of events to produce")) -> None:
    """Push sample events to Kafka topics (for testing the speed layer)."""
    _bootstrap()
    try:
        from confluent_kafka import Producer  # type: ignore[import-not-found]
    except ImportError as e:
        console.print(f"[red]confluent-kafka required: {e}[/]")
        raise typer.Exit(1) from e

    s = get_settings()
    p = Producer({"bootstrap.servers": s.kafka_bootstrap_servers})

    now = datetime.now(tz=UTC).isoformat()
    for i in range(count):
        payload = {
            "event_id": f"evt-{i:06d}",
            "session_id": f"sess-{i % 10:03d}",
            "customer_id": f"cust-{i % 25:03d}",
            "event_type": "PAGE_VIEW",
            "page_url": f"/products/{i % 50}",
            "timestamp": now,
        }
        p.produce(s.kafka_topic_clickstream, value=json.dumps(payload).encode("utf-8"))
    p.flush()
    console.print(f"[green]Produced {count} events to {s.kafka_topic_clickstream}[/]")


@app.command()
def batch() -> None:
    """Run the batch enrichment pipeline (CLV + funnel)."""
    _bootstrap()
    console.print("[cyan]Running batch enrichment (sample data)...[/]")
    demo()


if __name__ == "__main__":
    app()
