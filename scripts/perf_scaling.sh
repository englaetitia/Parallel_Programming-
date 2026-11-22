#!/usr/bin/env bash
# perf_scaling.sh - Part 4, experiments 2 and 3, ON THE CLUSTER (both VMs must be on and built).
#   strong: N = 512, 2048, 8192 ; strips and blocks ; P = 1 .. 4 ; placement --map-by node and --map-by slot
#   weak:   about 1024 x 1024 nodes per process: N = 1024 (P=1), 1448 (P=2), 2048 (P=4) ; map-by node
# Each run: --case 2 --r 0.24 --steps 500, repeated 3 times. Lines are appended to results/raw/scaling.txt
# with "exp=... map=... rep=..." in front. Runs already in the file are skipped (safe to stop and restart).
#
# Usage (repository root, on the VM that is first in 'hosts'):
#   bash scripts/perf_scaling.sh            # everything
#   bash scripts/perf_scaling.sh strong     # only strong scaling
#   bash scripts/perf_scaling.sh weak       # only weak scaling
#   bash scripts/perf_scaling.sh local      # only the runs that stay on the first VM (P = 1, or P = 2 with map-by slot)
# P never exceeds the slots in 'hosts' (2 per VM = 4 in total): no more processes than vCPUs.
cd "$(dirname "$0")/.." || exit 1
OUT=results/raw/scaling.txt
mkdir -p results/raw; touch "$OUT"
WHAT=${1:-all}
LOCAL_ONLY=0
if [ "$WHAT" = local ]; then LOCAL_ONLY=1; WHAT=all; fi
STEPS=500

run() {   # run <exp> <map> <rep> <decomp> <P> <N>
  local exp=$1 map=$2 rep=$3 decomp=$4 P=$5 N=$6 tag
  tag="exp=$exp map=$map rep=$rep"
  # "local" mode: only the runs whose processes all sit on the first VM (no traffic between the VMs):
  # P = 1, or P <= 2 slots with --map-by slot. Useful when the network between the VMs is bad.
  if [ "$LOCAL_ONLY" = 1 ] && ! { [ "$P" -eq 1 ] || { [ "$map" = slot ] && [ "$P" -le 2 ]; }; }; then return; fi
  if grep -q "^$tag decomp=$decomp P=$P .* N=$N " "$OUT"; then echo "skip $tag $decomp P=$P N=$N"; return; fi
  local line
  line=$(bash scripts/run_mpi.sh --map-by "$map" -np "$P" ./build/heat --decomp "$decomp" \
         --case 2 --N "$N" --r 0.24 --steps $STEPS) || { echo "FAILED: $tag $decomp P=$P N=$N"; return; }
  echo "$tag $line" | tee -a "$OUT"
}

if [ "$WHAT" = all ] || [ "$WHAT" = strong ]; then
  for N in 512 2048 8192; do
    for map in node slot; do
      for decomp in strips blocks; do
        for P in 1 2 3 4; do
          for rep in 1 2 3; do run strong $map $rep $decomp $P $N; done
        done
      done
    done
  done
fi
if [ "$WHAT" = all ] || [ "$WHAT" = weak ]; then
  for pair in "1 1024" "2 1448" "4 2048"; do
    set -- $pair
    for decomp in strips blocks; do
      for rep in 1 2 3; do run weak node $rep $decomp "$1" "$2"; done
    done
  done
fi
