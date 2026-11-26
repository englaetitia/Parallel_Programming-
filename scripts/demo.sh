#!/usr/bin/env bash
# demo.sh - the live demo, step by step. Run it on heat-laetitia from the repo root:
#     bash scripts/demo.sh
# It stops after each part ("Press Enter") so you can explain on the recording.
# Grids are small on purpose: each step across the VMs costs ~0.1 s of network, so every run takes 15-60 s.
# Pictures and the animation are written to demo_out/ (on heat-laetitia).
#
# Change N or P on request at the end:  bash scripts/demo.sh custom <case> <N> <P> <strips|blocks>
#     e.g.  bash scripts/demo.sh custom 1 128 3 strips

cd "$(dirname "$0")/.." || exit 1
mkdir -p demo_out
MPI="bash scripts/run_mpi.sh"
R=0.24

pause() { echo; read -r -p "---- Press Enter for the next part ----" _; clear; }
title() { echo; echo "=================================================================="; echo "  $*"; echo "=================================================================="; }
say()   { echo; echo ">>> $*"; }

# One parallel run compared byte by byte with the serial run, then a heat map.
compare_and_draw() {   # case N P decomp steps
    local k=$1 N=$2 P=$3 d=$4 s=$5
    local ser="demo_out/serial_c${k}_N${N}.bin" par="demo_out/${d}_c${k}_N${N}_P${P}.bin"
    say "Serial run (1 process):"
    ./build/heat --case "$k" --N "$N" --r $R --steps "$s" --out "$ser"
    say "Parallel run: $d, $P processes, spread over both VMs (--map-by node):"
    $MPI --map-by node -np "$P" ./build/heat --decomp "$d" --case "$k" --N "$N" --r $R --steps "$s" --out "$par"
    say "Byte-for-byte comparison of the two result files (cmp):"
    if cmp "$ser" "$par"; then echo "    IDENTICAL - the parallel result is exactly the serial one."; else echo "    DIFFERENT"; fi
    say "Heat map:"
    python3 scripts/heatmap.py "$par" "$N" "demo_out/${d}_c${k}_N${N}_P${P}.png"
}

if [ "${1:-}" = "custom" ]; then
    title "On request: case $2, N = $3, P = $4, $5"
    compare_and_draw "$2" "$3" "$4" "$5" 200
    exit 0
fi

# ---------------------------------------------------------------- Part 1
title "Part 1 - Our cluster: two VMs joined by Tailscale"
say "The two VMs on the tailnet:";            tailscale status | grep -E "heat-(laetitia|georges)"
say "The hostfile (2 slots per VM):";         cat hosts
say "Same program on both VMs (same md5):";   md5sum build/heat; ssh heat-georges "md5sum ~/heat/build/heat"
say "One mpirun, 4 processes, on both machines:"
$MPI --map-by node -np 4 hostname
pause

# ---------------------------------------------------------------- Part 2
title "Part 2 - Case 1 (all edges hot), blocks on 4 processes: same answer as serial"
compare_and_draw 1 32 4 blocks 200
pause

# ---------------------------------------------------------------- Part 3
title "Part 3 - Case 2 (top and bottom hot, sides cold), strips on 4 processes"
compare_and_draw 2 32 4 strips 200
pause

# ---------------------------------------------------------------- Part 4
title "Part 4 - The plate heating up over time (Case 2, blocks, 4 processes)"
for s in 20 80 300; do
    $MPI --map-by node -np 4 ./build/heat --decomp blocks --case 2 --N 32 --r $R --steps $s --out "demo_out/anim_$s.bin" > /dev/null
    echo "    computed $s steps"
done
python3 - <<'EOF'
import numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
N, steps = 32, [20, 80, 300]
U = [np.fromfile(f"demo_out/anim_{s}.bin", "<f8").reshape(N + 1, N + 1) for s in steps]
fig, axes = plt.subplots(1, 3, figsize=(11, 3.6))
for ax, u, s in zip(axes, U, steps):
    ax.imshow(u, origin="lower", extent=[0, 1, 0, 1], cmap="inferno", vmin=0, vmax=1)
    ax.set_title(f"after {s} steps (t = {s * 0.24 / N**2:.3f})"); ax.set_xticks([]); ax.set_yticks([])
plt.tight_layout(); plt.savefig("demo_out/case2_over_time.png", dpi=120); plt.close()
fig, ax = plt.subplots(figsize=(4.5, 4))
im = ax.imshow(U[0], origin="lower", extent=[0, 1, 0, 1], cmap="inferno", vmin=0, vmax=1)
def frame(i):
    im.set_data(U[i]); ax.set_title(f"Case 2 after {steps[i]} steps"); return [im]
FuncAnimation(fig, frame, frames=len(U)).save("demo_out/case2_animation.gif", writer=PillowWriter(fps=1))
print("saved demo_out/case2_over_time.png and demo_out/case2_animation.gif")
EOF
pause

# ---------------------------------------------------------------- Part 5
title "Part 5 - Changing N and P: same answer whatever the split"
for P in 2 3; do compare_and_draw 1 48 $P strips 200; done
pause

# ---------------------------------------------------------------- Part 6
title "Part 6 - Speed: N = 512, 200 steps, 1 process vs 4 processes on both VMs"
say "1 process:"
./build/heat --case 2 --N 512 --r $R --steps 200
say "4 processes, blocks, both VMs:"
$MPI --map-by node -np 4 ./build/heat --decomp blocks --case 2 --N 512 --r $R --steps 200
say "Look at t_comp and t_comm: computing takes a moment, communicating over Tailscale takes much longer"
say "(about 30 ms latency and 0.16 MB/s between the VMs). The report explains it with our model."
title "End of the demo. Pictures and animation are in demo_out/"
ls demo_out/*.png demo_out/*.gif
