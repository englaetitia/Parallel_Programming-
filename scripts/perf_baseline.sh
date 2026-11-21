#!/usr/bin/env bash
# perf_baseline.sh - Part 4, experiment 1: single-node baseline (serial, one VM).
# For N = 512, 1024, 2048, 4096, 8192: 500 steps at r = 0.24, repeated 3 times.
# Every summary line is appended (with the VM name in front) to results/raw/baseline_<vm>.txt.
# Already-done runs are skipped, so you can stop it (Ctrl+C) and start it again.
#
# Usage (repository root, in ONE VM):  bash scripts/perf_baseline.sh [N ...]
# Memory needed: 2 arrays of (N+1)^2 doubles  ->  N = 8192 needs about 1.1 GB free (check with: free -h).
cd "$(dirname "$0")/.." || exit 1
VM=$(hostname)
OUT=results/raw/baseline_${VM}.txt
mkdir -p results/raw; touch "$OUT"
SIZES=${*:-"512 1024 2048 4096 8192"}
for N in $SIZES; do
  for rep in 1 2 3; do
    if grep -q "^vm=$VM rep=$rep .* N=$N " "$OUT"; then echo "skip N=$N rep=$rep (already done)"; continue; fi
    line=$(./build/heat --case 2 --N "$N" --r 0.24 --steps 500) || { echo "run failed for N=$N"; exit 1; }
    echo "vm=$VM rep=$rep $line" | tee -a "$OUT"
  done
done
