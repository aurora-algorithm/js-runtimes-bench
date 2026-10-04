# js-runtimes-bench

Code and per-run results behind the Short "Which JavaScript runtime is fastest? Node vs Bun vs Deno": each runtime
returns the same 50 users as JSON, through its built-in server, the same Express app, and Postgres.
Rust (axum) was measured in the same session as a reference point; it isn't in the video.

## What is measured
- **Test 1 — built-in server:** `GET /users` returns the same 50 users as JSON. Node `node:http`, Bun `Bun.serve`,
  Deno `Deno.serve`, Rust axum. Responses are byte-identical across all four.
- **Test 2 — the same Express app** (`js/express.mjs`, Express 5) started by Node, Bun and Deno.
- **Test 3 — Postgres:** `GET /users-db` reads 50 rows starting at a random id from a 10,000-row table
  (`schema.sql`). JavaScript: node-postgres (`pg`), unchanged on every runtime. Rust: sqlx (`/users-db`, its most
  popular driver) and tokio-postgres + deadpool (`/users-pg`). Every pool holds 20 connections opened at startup.
- For every run: requests/second (per 0.5 s), latency percentiles, peak memory (RSS) of the server process.

## Results (median of 5 runs)
| Test | Server | req/s (median) | slowest–fastest run | typical (p50) | slowest 1% (p99) | peak memory |
|---|---|---|---|---|---|---|
| Built-in server | Node · node:http | 35,989 | 33,824–36,602 | 1.72 ms | 3.45 ms | 116.2 MiB |
| Built-in server | Bun · Bun.serve | 67,438 | 66,190–73,001 | 0.89 ms | 1.87 ms | 42.8 MiB |
| Built-in server | Deno · Deno.serve | 48,959 | 46,066–49,383 | 1.3 ms | 1.64 ms | 70.4 MiB |
| Built-in server | Rust · axum, 1 thread | 47,026 | 46,194–48,353 | 1.36 ms | 1.92 ms | 11.5 MiB |
| Built-in server | Rust · axum, all cores | 113,306 | 108,487–130,743 | 0.49 ms | 1.98 ms | 13.1 MiB |
| Express | Node | 25,571 | 23,718–25,989 | 2.43 ms | 4.9 ms | 122.8 MiB |
| Express | Bun | 35,882 | 34,717–37,019 | 1.62 ms | 3.77 ms | 94.5 MiB |
| Express | Deno | 18,631 | 18,365–19,499 | 3.31 ms | 6.2 ms | 167.8 MiB |
| Postgres | Node · pg | 12,083 | 11,168–12,209 | 5.32 ms | 7.21 ms | 210.4 MiB |
| Postgres | Bun · pg | 14,918 | 14,836–16,397 | 4.06 ms | 6.14 ms | 71.1 MiB |
| Postgres | Bun · Bun.sql | 14,897 | 13,396–15,532 | 4.26 ms | 6.44 ms | 55.8 MiB |
| Postgres | Deno · pg | 13,672 | 13,210–14,146 | 4.39 ms | 7.01 ms | 136.8 MiB |
| Postgres | Rust · sqlx, 1 thread | 13,436 | 13,117–13,824 | 4.74 ms | 6.69 ms | 12.1 MiB |
| Postgres | Rust · tokio-postgres, 1 thread | 19,556 | 17,657–20,870 | 3.26 ms | 4.08 ms | 12.0 MiB |
| Postgres | Rust · sqlx, all cores | 26,580 | 24,793–29,796 | 2.26 ms | 4.51 ms | 13.0 MiB |
| Postgres | Rust · tokio-postgres, all cores | 38,531 | 38,226–47,183 | 1.44 ms | 4.33 ms | 13.1 MiB |

Raw per-run files are in `results/`; exact versions in `results/versions.txt`.

## Method
- Apple M1 Pro (10 cores, 16 GB), macOS. Node 24.21, Bun 1.4.2, Deno 2.9.7, Rust 1.97.1, PostgreSQL 17.11, oha 1.16.
- oha with 64 connections: 10 s warm-up, then 20 s measured; 5 runs per configuration, alternating; median reported.
- A run only starts when the machine is quiet and is redone if background CPU was high during it (`run_all.sh`).

## Caveats
- **Threads.** Node, Bun and Deno run JavaScript on one thread by default; Rust's Tokio uses every core. Rust is
  measured both ways: one worker (`TOKIO_WORKER_THREADS=1`) and its default (all 10 cores, sharing the laptop with oha
  and Postgres). Tokio's single-threaded `current_thread` scheduler
  (`RUNTIME=current_thread`) measured the same in an earlier trial (47.2k vs 47.1k req/s on `/users`; not in `results/`). All-cores Rust is measured
  directly here (see the table).
- Multi-process scaling (Node `cluster`; Bun/Deno `reusePort`, which only load-balances on Linux) isn't tested.
- "One thread" means one JavaScript thread: the JS runtimes' helper and GC threads took the process slightly above one
  core in some tests (Bun + pg 109%, Bun.sql 102%, Deno + Express 103%); the one-worker Rust server
  stayed at 90–97%; all-cores Rust averaged 290–341% (oha and Postgres share the laptop).
- Every server opens its database pool at startup, so test 1 memory includes the pools too (JS: 20 connections; Rust: 40).
- Slowest 0.1% (p99.9), built-in server: Deno 2.07 ms, Bun 2.24 ms, Rust 1 thread 3.31 ms, Node 3.87 ms, Rust all cores 4.5 ms.
- Deno's handler parses the URL (`new URL(req.url)`, as in Deno's docs); Node compares `req.url` and Bun uses `routes`.
- Test 3 also measures each side's second driver: Bun's built-in `Bun.sql` (no faster than `pg` here) and Rust's
  tokio-postgres. `Bun.sql`, sqlx and tokio-postgres cache prepared statements; `pg` sends unnamed queries.
- The Rust server opens both of its pools (sqlx and deadpool, 40 connections), which slightly inflates its memory.
  It uses the system allocator; Bun uses mimalloc internally. Allocator swaps are a welcome PR.
- Bun 1.4 ported Bun's own code from Zig to Rust, but `Bun.serve` still runs on uWebSockets (C++) and
  JavaScriptCore, so test 1 is not "Bun's Rust vs axum".
- All 16 configurations were measured in one session, alternating, 5 runs each (`run_all.sh`).
- Test 3's popular-driver group uses the same driver (`pg`) on every JavaScript runtime; Bun.sql is measured separately.
- The load tool, the server and Postgres share one laptop. Compare the gaps, not the absolute numbers.
- After measuring, some long lines in `js/` were re-wrapped (line breaks only) so the code fits on a phone screen.

## Run it
```bash
psql -c 'CREATE DATABASE bench' && psql bench -f schema.sql
NODE_BIN=$(which node) ./run_all.sh          # about 40 minutes; RESUME=1 continues an interrupted run
python3 export_charts.py summary.json charts.json
```
