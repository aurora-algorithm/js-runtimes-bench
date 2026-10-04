#!/bin/bash
# Full suite: 5 alternating runs of every configuration. Needs Postgres with the bench DB (see README).
# Node, Bun and Deno serve JavaScript on one thread by default; Rust's Tokio uses every core by default.
# Rust is measured both ways: one worker thread (like-for-like) and all cores (its default).
# On a shared laptop, each run waits for a quiet machine and is redone if background CPU was too high.
set -euo pipefail
export DATABASE_URL="${DATABASE_URL:-postgres://$USER@localhost:5432/bench}"
QUIET_PCT=230     # max background CPU (sum of %, idle baseline here is ~200) before a run starts
DISTURBED_PCT=280 # a run averaging more background CPU than this is discarded and redone
ATTEMPTS=4

NODE_BIN="${NODE_BIN:-node}"

(cd rust-server && cargo build --release -q)
(cd js && npm ci --silent)
mkdir -p results
# RESUME=1 keeps finished runs (e.g. after an interruption) and only measures the missing ones.
[ "${RESUME:-0}" = 1 ] || rm -f results/*.json
{ echo "node $($NODE_BIN --version)"; bun --version | sed 's/^/bun /'; deno --version | head -1; rustc --version
  oha --version; psql "$DATABASE_URL" -tAc 'show server_version' | sed 's/^/postgres /'; } > results/versions.txt.new && mv results/versions.txt.new results/versions.txt

NODE="cd js && exec $NODE_BIN node-http.mjs"
BUN='cd js && exec bun bun-serve.ts'
DENO='cd js && exec deno run -A deno-serve.ts'
RUST='exec env TOKIO_WORKER_THREADS=1 rust-server/target/release/rust-server'
RUST_MT='exec rust-server/target/release/rust-server'
BUN_SQL='cd js && exec bun bun-sql.ts'
NODE_EXPRESS="cd js && PORT=8094 exec $NODE_BIN express.mjs"
BUN_EXPRESS='cd js && PORT=8095 exec bun express.mjs'
DENO_EXPRESS='cd js && PORT=8096 exec deno run -A express.mjs'

background_cpu() {
  ps -axo %cpu=,comm= | awk '/postgres|oha|awk|ps$|perl|python3/ { next } { s += $1 } END { printf "%.0f", s }'
}

wait_quiet() {
  local calm=0
  while [ "$calm" -lt 5 ]; do
    if [ "$(background_cpu)" -le "$QUIET_PCT" ]; then calm=$((calm + 1)); else calm=0; fi
    sleep 1
  done
}

measure() { # name command port path run
  [ -f "results/$1_${4#/}_run$5.json" ] && return 0
  for attempt in $(seq 1 $ATTEMPTS); do
    wait_quiet
    ./load.sh "$1" "$2" "$3" "$4" "$5"
    local bg; bg=$(python3 -c "import json;print(json.load(open('results/$1_${4#/}_mem_run$5.json'))['bg_cpu_pct'])")
    if [ "$bg" -le "$DISTURBED_PCT" ]; then return 0; fi
    echo "  $1 $4 run $5 disturbed (background ${bg}%), retry $attempt" >&2
  done
  echo "  $1 $4 run $5 kept despite background load" >&2
}

for run in 1 2 3 4 5; do
  measure node    "$NODE"    8091 /users "$run"
  measure bun     "$BUN"     8092 /users "$run"
  measure deno    "$DENO"    8093 /users "$run"
  measure rust    "$RUST"    8082 /users "$run"
  measure rust-mt "$RUST_MT" 8082 /users "$run"
  measure node-express "$NODE_EXPRESS" 8094 /users "$run"
  measure bun-express  "$BUN_EXPRESS"  8095 /users "$run"
  measure deno-express "$DENO_EXPRESS" 8096 /users "$run"
  measure node    "$NODE"    8091 /users-db "$run"
  measure bun     "$BUN"     8092 /users-db "$run"
  measure bun-sql "$BUN_SQL" 8097 /users-db "$run"
  measure deno    "$DENO"    8093 /users-db "$run"
  measure rust    "$RUST"    8082 /users-db "$run"
  measure rust    "$RUST"    8082 /users-pg "$run"
  measure rust-mt "$RUST_MT" 8082 /users-db "$run"
  measure rust-mt "$RUST_MT" 8082 /users-pg "$run"
  echo "run $run done"
done
