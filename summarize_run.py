"""Turn one run's raw data into a compact results file.

usage: summarize_run.py <oha.csv> <samples.txt> <duration_s> <out.json>

oha.csv     per-request CSV from `oha --output-format csv` (request-start, ..., request-duration, bytes, status)
samples.txt one line per 0.25 s: "<elapsed_s> <rss_kb> <server_cpu%> <postgres_cpu%> <background_cpu%>"
"""
import csv
import json
import sys

BUCKET_S = 0.5
PERCENTILES = [50, 90, 99, 99.9]


def percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * p / 100
    lo = int(k)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (k - lo)


def main() -> None:
    csv_path, samples_path, duration_s, out_path = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
    buckets = [0] * int(duration_s / BUCKET_S)
    durations: list[float] = []
    total = ok = 0
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            start = float(row["request-start"])
            if start >= duration_s:
                continue
            total += 1
            if row["status"] != "200":
                continue
            ok += 1
            durations.append(float(row["request-duration"]))
            buckets[min(int(start / BUCKET_S), len(buckets) - 1)] += 1
    if total == 0:
        raise SystemExit(f"{csv_path}: no requests recorded")
    durations.sort()

    samples = []
    with open(samples_path) as f:
        for line in f:
            parts = line.split()
            if len(parts) == 5:
                t, rss, cpu, pg, bg = (float(x) for x in parts)
                samples.append({"t": round(t, 2), "rss_mb": round(rss / 1024, 2), "cpu": cpu, "pg_cpu": pg, "bg_cpu": bg})
    if not samples:
        raise SystemExit(f"{samples_path}: no memory samples")

    result = {
        "summary": {
            "requestsPerSec": ok / duration_s,
            "total": total,
            "successRate": ok / total,
        },
        "latencyPercentiles": {f"p{p:g}": percentile(durations, p) for p in PERCENTILES},
        "throughput_series": {"bucket_s": BUCKET_S, "rps": [n / BUCKET_S for n in buckets]},
        "memory_series": samples,
        "peak_kb": max(s["rss_mb"] for s in samples) * 1024,
        "avg_cpu_pct": sum(s["cpu"] for s in samples) / len(samples),
        "pg_cpu_pct": sum(s["pg_cpu"] for s in samples) / len(samples),
        "bg_cpu_pct": sum(s["bg_cpu"] for s in samples) / len(samples),
    }
    with open(out_path, "w") as f:
        json.dump(result, f)


if __name__ == "__main__":
    main()
