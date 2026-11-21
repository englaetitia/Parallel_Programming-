#!/usr/bin/env bash
# check_identical.sh - Steps 9-10: are the parallel results EXACTLY the same as the serial ones?
#
# For every case (1, 2, V), two grid sizes (an even and an odd N, so the rows don't split evenly)
# and P = 1, 2, 3, 4 (and 6 for blocks: a 3x2 grid), it runs the serial version and the parallel one,
# then compares the two output files byte by byte with 'cmp'. One line per test: OK or DIFFERENT.
#
# A run that fails to start (e.g. more processes than slots) is reported as FAILED, never compared with an old file.
#
# Usage (from the repository root, after building):
#   bash scripts/check_identical.sh                      # on ONE VM (default: mpirun --oversubscribe)
#   MPIRUN="bash scripts/run_mpi.sh --oversubscribe" bash scripts/check_identical.sh   # cluster (both VMs);
#        --oversubscribe because the P = 6 tests need more than the 4 slots of 'hosts' (correctness only)
cd "$(dirname "$0")/.." || exit 1
MPIRUN=${MPIRUN:-"mpirun --oversubscribe"}
OUT=build/check
mkdir -p "$OUT"
STEPS=200
fails=0; total=0
for kase in 1 2 V; do
  for N in 64 67; do
    ./build/heat --case $kase --N $N --r 0.24 --steps $STEPS --out "$OUT/serial_${kase}_${N}.bin" > /dev/null || exit 1
    for decomp in strips blocks; do
      for P in 1 2 3 4 6; do
        [ "$decomp" = strips ] && [ $P -eq 6 ] && continue
        f="$OUT/${decomp}_${kase}_${N}_P${P}.bin"
        rm -f "$f"                    # never compare with an old file from an earlier run
        total=$((total + 1))
        if ! line=$($MPIRUN -np $P ./build/heat --decomp $decomp --case $kase --N $N --r 0.24 --steps $STEPS --out "$f"); then
          printf 'FAILED     case=%s N=%-3s %-6s P=%s (the run did not start or crashed)\n' $kase $N $decomp $P
          fails=$((fails + 1))
          continue
        fi
        layout=$(echo "$line" | tr ' ' '\n' | grep '^layout=' | cut -d= -f2)
        if cmp -s "$OUT/serial_${kase}_${N}.bin" "$f"; then
          printf 'OK         case=%s N=%-3s %-6s P=%s (%s)\n' $kase $N $decomp $P "$layout"
        else
          printf 'DIFFERENT  case=%s N=%-3s %-6s P=%s (%s)\n' $kase $N $decomp $P "$layout"
          fails=$((fails + 1))
        fi
      done
    done
  done
done
echo "$((total - fails)) / $total identical to the serial result"
[ $fails -eq 0 ]
