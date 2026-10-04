"""Builds summary.json and the video's chart data from results/*.json.

usage: export_charts.py <summary.json> <charts.json>
"""
import json
import re
import statistics
import sys

RUNS = range(1, 6)
CONFIGS = {
    "node_json": ("node", "users", "Node · node:http"),
    "bun_json": ("bun", "users", "Bun · Bun.serve"),
    "deno_json": ("deno", "users", "Deno · Deno.serve"),
    "rust_json": ("rust", "users", "Rust · axum (1 worker thread)"),
    "node_express": ("node-express", "users", "Node · Express"),
    "bun_express": ("bun-express", "users", "Bun · Express"),
    "deno_express": ("deno-express", "users", "Deno · Express"),
    "node_pg": ("node", "users-db", "Node · pg"),
    "bun_pg": ("bun", "users-db", "Bun · pg"),
    "deno_pg": ("deno", "users-db", "Deno · pg"),
    "rust_sqlx": ("rust", "users-db", "Rust · sqlx (1 worker thread)"),
    "rust_tokio_pg": ("rust", "users-pg", "Rust · tokio-postgres (1 worker thread)"),
    "bun_sql": ("bun-sql", "users-db", "Bun · Bun.sql"),
    "rustmt_json": ("rust-mt", "users", "Rust · axum (all cores)"),
    "rustmt_sqlx": ("rust-mt", "users-db", "Rust · sqlx (all cores)"),
    "rustmt_tokio_pg": ("rust-mt", "users-pg", "Rust · tokio-postgres (all cores)"),
}
SETUP = {
    "machine": "MacBook Pro, M1 Pro (10-core), 16 GB, macOS",
    "load": "64 connections · 10 s warm-up · 20 s measured · 5 alternating runs, median",
    "threads": "JS runtimes: one process (their default); Rust: one worker thread and all cores (its default)",
    "db": "users table, 10,000 rows · 50 rows from a random start by primary key · 20-connection pool opened at startup",
    "caveat": "Load tool, server and Postgres share one laptop",
}


def versions() -> dict:
    """Tool versions as run_all.sh recorded them, e.g. {"node": "24.21.0", "bun": "1.4.2", ...}."""
    found = {}
    with open("results/versions.txt") as f:
        for line in f:
            m = re.match(r"(\w+)\s+v?(\d+(?:\.\d+)+)", line)
            if m:
                found[m.group(1)] = m.group(2)
    missing = {"node", "bun", "deno", "oha", "postgres"} - found.keys()
    if missing:
        sys.exit(f"results/versions.txt lacks {sorted(missing)}")
    return found


def load(lang: str, route: str, run: int) -> dict:
    with open(f"results/{lang}_{route}_run{run}.json") as f:
        return json.load(f)


def main() -> None:
    summary_path, charts_path = sys.argv[1], sys.argv[2]
    summary, charts = {}, {}
    for key, (lang, route, label) in CONFIGS.items():
        runs = [load(lang, route, r) for r in RUNS]
        rps = [r["summary"]["requestsPerSec"] for r in runs]
        median_rps = statistics.median(rps)
        median_run = min(runs, key=lambda r: abs(r["summary"]["requestsPerSec"] - median_rps))
        pct = {p: statistics.median(r["latencyPercentiles"][p] for r in runs) * 1000 for p in ("p50", "p90", "p99", "p99.9")}
        summary[key] = {
            "label": label,
            "rps": round(median_rps),
            "rps_min": round(min(rps)),
            "rps_max": round(max(rps)),
            "p50_ms": round(pct["p50"], 2),
            "p99_ms": round(pct["p99"], 2),
            "p99_9_ms": round(pct["p99.9"], 2),
            "success": min(r["summary"]["successRate"] for r in runs),
            "peak_mb": round(statistics.median(r["peak_kb"] for r in runs) / 1024, 1),
            "server_cpu_pct": round(statistics.median(r["avg_cpu_pct"] for r in runs)),
            "postgres_cpu_pct": round(statistics.median(r["pg_cpu_pct"] for r in runs)),
            "background_cpu_pct": round(statistics.median(r["bg_cpu_pct"] for r in runs)),
        }
        charts[key] = {
            "bucket_s": median_run["throughput_series"]["bucket_s"],
            "throughput_runs": [[round(v) for v in r["throughput_series"]["rps"]] for r in runs],
            "median_run": runs.index(median_run),
            "latency_ms": {p: round(v, 3) for p, v in pct.items()},
            "memory": [[s["t"], s["rss_mb"]] for s in median_run["memory_series"]],
        }
    summary["setup"] = {**SETUP, "versions": versions()}
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    with open(charts_path, "w") as f:
        json.dump(charts, f)


if __name__ == "__main__":
    main()
