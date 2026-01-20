#!/usr/bin/env python3
"""
Database monitoring dashboard for Kernel email client.

Usage:
    # Show current status
    python scripts/monitor_db.py status

    # Run continuous monitoring
    python scripts/monitor_db.py watch --interval 5

    # Export metrics to JSON
    python scripts/monitor_db.py metrics --output metrics.json

    # Run health checks
    python scripts/monitor_db.py health
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.core.database import EngineManager, EmailRepository
from src.core.database.performance.health import HealthChecker, HealthStatus
from src.core.database.performance.metrics import get_metrics_collector
from src.utils.paths import DATABASE_PATH

console = Console()


async def show_status(db_path: Path) -> int:
    """Show current database status."""
    engine_mgr = EngineManager(db_path)
    repo = EmailRepository(engine_mgr)

    try:
        # Get pool stats
        pool_stats = await engine_mgr.get_pool_stats()

        # Create status display
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="pool", size=10),
            Layout(name="database", size=10),
        )

        # Header
        layout["header"].update(
            Panel(
                f"[bold cyan]Kernel Database Monitor[/bold cyan]\n"
                f"Database: {db_path.name}",
                border_style="cyan",
            )
        )

        # Pool stats table
        pool_table = Table(title="Connection Pool", show_header=True)
        pool_table.add_column("Metric", style="cyan")
        pool_table.add_column("Value", style="green")

        pool_table.add_row(
            "Status", "✓ Healthy" if pool_stats.get("healthy") else "✗ Unhealthy"
        )
        pool_table.add_row("Pool Size", str(pool_stats.get("pool_size", "N/A")))
        pool_table.add_row("Checked Out", str(pool_stats.get("checked_out", "N/A")))
        pool_table.add_row(
            "Overflow", str(pool_stats.get("overflow_connections", "N/A"))
        )

        layout["pool"].update(Panel(pool_table, border_style="blue"))

        # Database stats table
        db_table = Table(title="Database", show_header=True)
        db_table.add_column("Metric", style="cyan")
        db_table.add_column("Value", style="green")

        db_table.add_row("Path", str(db_path))
        db_table.add_row("Size", f"{pool_stats.get('database_size_mb', 0):.2f} MB")
        db_table.add_row("Journal Mode", pool_stats.get("journal_mode", "N/A"))

        layout["database"].update(Panel(db_table, border_style="blue"))

        console.print(layout)

        return 0

    finally:
        await engine_mgr.close()


async def show_health(db_path: Path) -> int:
    """Run and display health checks."""
    engine_mgr = EngineManager(db_path)
    repo = EmailRepository(engine_mgr)
    checker = HealthChecker(engine_mgr, repo)

    try:
        console.print("[cyan]Running health checks...[/cyan]\n")

        health = await checker.check_all()

        # Overall status
        status_color = {
            HealthStatus.HEALTHY: "green",
            HealthStatus.DEGRADED: "yellow",
            HealthStatus.UNHEALTHY: "red",
            HealthStatus.UNKNOWN: "gray",
        }[health.status]

        console.print(
            Panel(
                f"[bold {status_color}]{health.status.value.upper()}[/bold {status_color}]",
                title="Overall Status",
                border_style=status_color,
            )
        )
        console.print()

        # Individual checks
        table = Table(title="Health Checks", show_header=True)
        table.add_column("Check", style="cyan")
        table.add_column("Status", style="white")
        table.add_column("Message", style="white")
        table.add_column("Duration", justify="right")

        for check in health.checks:
            status_icon = {
                HealthStatus.HEALTHY: "✓",
                HealthStatus.DEGRADED: "⚠",
                HealthStatus.UNHEALTHY: "✗",
                HealthStatus.UNKNOWN: "?",
            }[check.status]

            status_text = Text()
            status_text.append(status_icon, style=status_color)
            status_text.append(f" {check.status.value}")

            table.add_row(
                check.name,
                status_text,
                check.message,
                f"{check.duration_ms:.1f}ms",
            )

            # Show details for failed checks
            if check.status != HealthStatus.HEALTHY and check.details:
                console.print("  [dim]Details:[/dim]")
                for key, value in check.details.items():
                    console.print(f"    {key}: {value}")

        console.print(table)

        return 0 if health.is_healthy else 1

    finally:
        await engine_mgr.close()


async def show_metrics(output_file: Optional[Path] = None) -> int:
    """Display or export metrics."""
    collector = get_metrics_collector()
    collector = get_metrics_collector()
    metrics = collector.get_all_metrics()

    if output_file:
        # Export to JSON
        with open(output_file, "w") as f:
            json.dump(metrics, f, indent=2, default=str)
        console.print(f"[green]✓ Metrics exported to {output_file}[/green]")
        return 0

    # Display in console
    console.print(Panel("[bold cyan]Database Metrics[/bold cyan]", border_style="cyan"))
    console.print()

    # Counters
    if metrics["counters"]:
        table = Table(title="Counters", show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right", style="green")

        for name, value in sorted(metrics["counters"].items()):
            table.add_row(name, f"{value:,.0f}")

        console.print(table)
        console.print()

    # Gauges
    if metrics["gauges"]:
        table = Table(title="Gauges", show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right", style="green")

        for name, value in sorted(metrics["gauges"].items()):
            table.add_row(name, f"{value:.2f}")

        console.print(table)
        console.print()

    # Timers
    if metrics["timers"]:
        table = Table(title="Timers (ms)", show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Count", justify="right")
        table.add_column("Avg", justify="right")
        table.add_column("P95", justify="right")
        table.add_column("P99", justify="right")
        table.add_column("Max", justify="right")

        for name, stats in sorted(metrics["timers"].items()):
            if stats:
                table.add_row(
                    name,
                    str(stats.count),
                    f"{stats.avg * 1000:.2f}",
                    f"{stats.p95 * 1000:.2f}",
                    f"{stats.p99 * 1000:.2f}",
                    f"{stats.max * 1000:.2f}",
                )

        console.print(table)

    return 0


async def watch_status(db_path: Path, interval: int) -> int:
    """Continuously monitor status."""
    engine_mgr = EngineManager(db_path)
    repo = EmailRepository(engine_mgr)
    checker = HealthChecker(engine_mgr, repo)

    def generate_display():
        """Generate display layout."""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="status", size=8),
            Layout(name="metrics", size=12),
        )

        # Header with timestamp
        layout["header"].update(
            Panel(
                f"[bold cyan]Kernel Database Monitor (Live)[/bold cyan]\n"
                f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                border_style="cyan",
            )
        )

        # Status panel
        try:
            # Note: This is sync, health check should be cached
            status_text = "[yellow]Checking...[/yellow]"
            layout["status"].update(
                Panel(status_text, title="Status", border_style="yellow")
            )
        except Exception as e:
            console.print(f"[red]✗ Error checking status: {e}[/red]")

        # Metrics panel
        collector = get_metrics_collector()
        metrics = collector.get_all_metrics()

        metrics_table = Table(show_header=True, box=None)
        metrics_table.add_column("Metric", style="cyan")
        metrics_table.add_column("Value", justify="right", style="green")

        # Show key counters
        for name, value in sorted(metrics["counters"].items())[:5]:
            metrics_table.add_row(name, f"{value:,.0f}")

        layout["metrics"].update(
            Panel(metrics_table, title="Top Metrics", border_style="blue")
        )

        return layout

    try:
        with Live(generate_display(), refresh_per_second=1) as live:
            while True:
                await asyncio.sleep(interval)
                live.update(generate_display())

    except KeyboardInterrupt:
        console.print("\n[yellow]Monitoring stopped[/yellow]")
        return 0

    finally:
        await engine_mgr.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Database monitoring dashboard for Kernel",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Status command
    status_parser = subparsers.add_parser("status", help="Show current status")
    status_parser.add_argument(
        "--db-path",
        type=Path,
        default=DATABASE_PATH,
        help="Database file path",
    )

    # Health command
    health_parser = subparsers.add_parser("health", help="Run health checks")
    health_parser.add_argument(
        "--db-path",
        type=Path,
        default=DATABASE_PATH,
        help="Database file path",
    )

    # Metrics command
    metrics_parser = subparsers.add_parser("metrics", help="Show metrics")
    metrics_parser.add_argument(
        "--output",
        type=Path,
        help="Export metrics to JSON file",
    )

    # Watch command
    watch_parser = subparsers.add_parser("watch", help="Continuous monitoring")
    watch_parser.add_argument(
        "--db-path",
        type=Path,
        default=DATABASE_PATH,
        help="Database file path",
    )
    watch_parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Update interval in seconds",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Execute command
    try:
        if args.command == "status":
            return asyncio.run(show_status(args.db_path))

        elif args.command == "health":
            return asyncio.run(show_health(args.db_path))

        elif args.command == "metrics":
            return asyncio.run(show_metrics(args.output))

        elif args.command == "watch":
            return asyncio.run(watch_status(args.db_path, args.interval))

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        return 130
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
