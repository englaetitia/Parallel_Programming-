#!/usr/bin/env python3
"""analyze_perf.py - Part 4: turn the raw run lines into tables and plots, with a performance model.

Reads results/raw/baseline_*.txt and results/raw/scaling.txt (written by perf_baseline.sh / perf_scaling.sh).
Uses the MEDIAN of the repeats of each configuration and prints the spread (max - min) / median.
Writes:
  results/perf_summary.csv       one line per configuration: medians, speed-up, efficiency, comm share, model
  results/speedup_N<N>.png       speed-up S(P) = T1/TP, measured (markers) and model (dotted), for each N
  results/efficiency_N<N>.png    efficiency E(P) = S(P)/P
  results/model_vs_measured.png  measured time per step against the model, every configuration
  results/comm_share.png         fraction of the time spent in the halo exchange
  results/weak_scaling.png       run time vs P at fixed work per process (when the weak runs exist)

Performance model (Task 8.2, made exact for our layouts), time per step = max over the processes of
    compute: c(N) x (number of interior nodes the process owns)
  + exchange: for each MPI_Sendrecv of the step, max(cost of the message sent, cost of the message received),
              cost of a message of m bytes = ts + m * tw * k
  - ts, tw: our ping-pong numbers (Step 5): between the VMs, or inside one VM, depending on where the partner runs;
  - k = number of messages crossing the network in the same direction during that Sendrecv (they share the link);
  - placement as Open MPI does it with 2 slots per VM: --map-by node -> rank r on VM r % 2,
    --map-by slot -> ranks 0, 1 on the first VM, 2, 3 on the second;
  - c(N) = seconds per node update, measured by the P = 1 runs of the same experiment (on the first VM, where rank 0 runs).
Usage: python3 scripts/analyze_perf.py [--ts 0.029 --tw 6.7e-6] [--scaling results/raw/scaling.txt]
"""
import argparse, glob, math, os, statistics as st
from collections import defaultdict
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ap = argparse.ArgumentParser()
ap.add_argument("--ts", type=float, default=29.0e-3, help="latency between the VMs, s (Step 5: 29.0 ms)")
ap.add_argument("--tw", type=float, default=6.7e-6, help="time per byte between the VMs, s (Step 5: 6.7 us/byte)")
ap.add_argument("--ts-local", type=float, default=0.014e-3, help="latency inside one VM (Step 5: 0.014 ms)")
ap.add_argument("--tw-local", type=float, default=1 / 2554e6, help="time per byte inside one VM (Step 5: 2554 MB/s)")
ap.add_argument("--slots", type=int, default=2, help="processes per VM (hosts file)")
ap.add_argument("--scaling", default="results/raw/scaling.txt")
a = ap.parse_args()

def parse(path):
    rows = []
    for line in open(path):
        kv = dict(x.split("=", 1) for x in line.split() if "=" in x)
        if "t_total" in kv:
            rows.append(kv)
    return rows

os.makedirs("results", exist_ok=True)

# ---- 1. Baselines (serial, one VM each) ----------------------------------------------------------
base = defaultdict(list)
for f in sorted(glob.glob("results/raw/baseline_*.txt")):
    for kv in parse(f):
        N, steps = int(kv["N"]), int(kv["steps"])
        base[(kv["vm"], N)].append(float(kv["t_total"]) / (steps * (N - 1) ** 2))
if base:
    print("Baseline (serial, one process, 500 steps): time per node update, median of the repeats")
    for (vm, N), v in sorted(base.items()):
        print(f"  {vm:15s} N={N:5d}  {st.median(v)*1e9:6.3f} ns/node   spread {100*(max(v)-min(v))/st.median(v):5.1f}%")
    print()

# ---- 2. Scaling runs: medians --------------------------------------------------------------------
if not os.path.exists(a.scaling):
    raise SystemExit(f"no {a.scaling} yet (run scripts/perf_scaling.sh on the cluster)")
groups = defaultdict(list)
for kv in parse(a.scaling):
    key = (kv["exp"], kv["map"], kv["decomp"], int(kv["P"]), int(kv["N"]))
    groups[key].append(dict(t=float(kv["t_total"]), comp=float(kv["t_comp"]), comm=float(kv["t_comm"]),
                            steps=int(kv["steps"]), layout=kv.get("layout", "")))
med = {}
for key, runs in groups.items():
    runs.sort(key=lambda r: r["t"])
    mid = runs[len(runs) // 2]                       # the median run (for comp / comm)
    tt = [r["t"] for r in runs]
    med[key] = dict(t=st.median(tt), comp=mid["comp"], comm=mid["comm"], steps=mid["steps"], n=len(runs),
                    layout=mid["layout"], spread=(max(tt) - min(tt)) / st.median(tt))

# c(N) from the P = 1 runs of the scaling experiment itself (same VM as rank 0, same conditions)
c_of_N = defaultdict(list)
for (exp, map_, decomp, P, N), m in med.items():
    if P == 1:
        c_of_N[N].append(m["t"] / (m["steps"] * (N - 1) ** 2))
c_of_N = {N: st.median(v) for N, v in c_of_N.items()}
def c_for(N):
    if N in c_of_N:
        return c_of_N[N]
    near = min(c_of_N, key=lambda k: abs(math.log(k / N)))   # closest measured size
    return c_of_N[near]
print("Compute rate from the P = 1 runs (rank 0's VM): " +
      ", ".join(f"N={N}: {c*1e9:.2f} ns/node" for N, c in sorted(c_of_N.items())) + "\n")

# ---- 3. Model --------------------------------------------------------------------------------------
def split(n, parts, k):
    base, extra = divmod(n, parts)
    return base + (1 if k < extra else 0)

def dims_create(P):                                   # same result as MPI_Dims_create for 2D (dims[0] >= dims[1])
    best = 1
    for k in range(1, int(math.isqrt(P)) + 1):
        if P % k == 0:
            best = k
    return P // best, best

def vm_of(rank, P, map_):
    return rank % 2 if map_ == "node" else min(rank // a.slots, 1)

def model_step(decomp, P, N, map_):
    """Predicted time of one step (s): max over ranks of compute + exchanges."""
    c = c_for(N)
    if decomp == "strips":
        px, py = 1, P
        coords = [(0, r) for r in range(P)]
    else:
        px, py = dims_create(P)
        coords = [(r // py, r % py) for r in range(P)]       # MPI_Cart_coords, row-major, reorder = 0
    rank_at = {xy: r for r, xy in enumerate(coords)}
    def nb(r, dx, dy):
        x, y = coords[r]
        return rank_at.get((x + dx, y + dy))               # None = MPI_PROC_NULL
    def size(r, axis):                                     # bytes of one halo message of rank r
        x, y = coords[r]
        if decomp == "strips":
            return 8 * (N + 1)                             # a whole row, boundary columns included
        nx, ny = split(N - 1, px, x), split(N - 1, py, y)
        return 8 * (nx if axis == "y" else ny)
    # the Sendrecv phases of one step: (direction of the send, axis)
    phases = [((0, +1), "y"), ((0, -1), "y")] if decomp == "strips" else \
             [((0, +1), "y"), ((0, -1), "y"), ((+1, 0), "x"), ((-1, 0), "x")]
    if decomp == "strips":   # in strips the "y" neighbours are ranks r +/- 1 (coords (0, r))
        pass
    comm = [0.0] * P
    for (dx, dy), axis in phases:
        # how many messages cross the network in each direction during this phase (they share the link)
        cross = defaultdict(int)
        for r in range(P):
            d = nb(r, dx, dy)
            if d is not None and vm_of(r, P, map_) != vm_of(d, P, map_):
                cross[(vm_of(r, P, map_), vm_of(d, P, map_))] += 1
        def cost(src, dst):
            if src is None or dst is None:
                return 0.0
            m = size(src, axis)
            vs, vd = vm_of(src, P, map_), vm_of(dst, P, map_)
            if vs == vd:
                return a.ts_local + m * a.tw_local
            return a.ts + m * a.tw * cross[(vs, vd)]
        for r in range(P):
            send_to, recv_from = nb(r, dx, dy), nb(r, -dx, -dy)
            comm[r] += max(cost(r, send_to), cost(recv_from, r))
    times = []
    for r in range(P):
        x, y = coords[r]
        nodes = (N - 1) * split(N - 1, P, r) if decomp == "strips" else split(N - 1, px, x) * split(N - 1, py, y)
        times.append(c * nodes + comm[r])
    return max(times)

# ---- 4. Table --------------------------------------------------------------------------------------
with open("results/perf_summary.csv", "w") as f:
    f.write("exp,map,decomp,P,N,layout,runs,t_median_s,spread_pct,t_per_step_ms,model_per_step_ms,model_over_measured,"
            "speedup,efficiency,comm_share\n")
    print(f"{'exp':6} {'map':4} {'decomp':6} {'P':>2} {'N':>5} {'layout':>6} {'t_med(s)':>9} {'spread':>7} "
          f"{'S(P)':>6} {'E(P)':>5} {'comm%':>6} {'meas/step':>10} {'model/step':>11}")
    for key in sorted(med, key=lambda k: (k[0], k[4], k[1], k[2], k[3])):
        exp, map_, decomp, P, N = key
        m = med[key]
        t1 = med.get((exp, map_, decomp, 1, N), {}).get("t") if exp == "strong" else None
        S = t1 / m["t"] if t1 else float("nan")
        E = S / P if t1 else float("nan")
        share = m["comm"] / m["t"] if m["t"] else 0.0
        meas = m["t"] / m["steps"]
        mod = model_step(decomp, P, N, map_)
        print(f"{exp:6} {map_:4} {decomp:6} {P:2d} {N:5d} {m['layout']:>6} {m['t']:9.3f} {100*m['spread']:6.1f}% "
              f"{S:6.2f} {E:5.2f} {100*share:5.1f}% {meas*1e3:7.1f} ms {mod*1e3:8.1f} ms")
        f.write(f"{exp},{map_},{decomp},{P},{N},{m['layout']},{m['n']},{m['t']:.6f},{100*m['spread']:.2f},"
                f"{meas*1e3:.4f},{mod*1e3:.4f},{mod/meas:.3f},{S:.4f},{E:.4f},{share:.4f}\n")

# ---- 5. Plots --------------------------------------------------------------------------------------
strongN = sorted({k[4] for k in med if k[0] == "strong"})
styles = {("strips", "node"): ("o-", "C0"), ("strips", "slot"): ("o--", "C1"),
          ("blocks", "node"): ("s-", "C2"), ("blocks", "slot"): ("s--", "C3")}
for N in strongN:
    for what in ("speedup", "efficiency"):
        plt.figure(figsize=(6, 4.5))
        for (decomp, map_), (sty, col) in styles.items():
            Ps = sorted(k[3] for k in med if k[0] == "strong" and k[1] == map_ and k[2] == decomp and k[4] == N)
            if 1 not in Ps:
                continue
            t1 = med[("strong", map_, decomp, 1, N)]["t"]
            S = [t1 / med[("strong", map_, decomp, P, N)]["t"] for P in Ps]
            y = S if what == "speedup" else [s / P for s, P in zip(S, Ps)]
            plt.plot(Ps, y, sty, color=col, label=f"{decomp}, map-by {map_}")
            m1 = model_step(decomp, 1, N, map_)
            Sm = [m1 / model_step(decomp, P, N, map_) for P in Ps]
            ym = Sm if what == "speedup" else [s / P for s, P in zip(Sm, Ps)]
            plt.plot(Ps, ym, ":", color=col, alpha=0.8, label=f"model {decomp}, {map_}")
        if what == "speedup":
            plt.plot([1, 4], [1, 4], "k-", lw=0.6, alpha=0.4, label="ideal")
        plt.yscale("log")
        plt.xlabel("number of processes P"); plt.ylabel("S(P) = T1 / TP (log scale)" if what == "speedup" else "E(P) = S(P) / P (log scale)")
        plt.title(f"Strong scaling, N = {N}, 500 steps"); plt.grid(alpha=0.3, which="both"); plt.legend(fontsize=7)
        plt.tight_layout(); plt.savefig(f"results/{what}_N{N}.png", dpi=150); plt.close()

plt.figure(figsize=(6, 5))
for (decomp, map_), (sty, col) in styles.items():
    pts = [(model_step(decomp, k[3], k[4], map_) * 1e3, med[k]["t"] / med[k]["steps"] * 1e3)
           for k in med if k[0] == "strong" and k[1] == map_ and k[2] == decomp]
    if pts:
        plt.scatter([p[0] for p in pts], [p[1] for p in pts], marker=sty[0], color=col, label=f"{decomp}, {map_}")
lo, hi = 0.05, 5000
plt.plot([lo, hi], [lo, hi], "k--", lw=0.8, label="measured = model")
plt.xscale("log"); plt.yscale("log"); plt.xlim(lo, hi); plt.ylim(lo, hi)
plt.xlabel("model: time per step (ms)"); plt.ylabel("measured: time per step (ms)")
plt.title("Model against measurement (strong scaling)"); plt.grid(alpha=0.3, which="both"); plt.legend(fontsize=7)
plt.tight_layout(); plt.savefig("results/model_vs_measured.png", dpi=150); plt.close()

plt.figure(figsize=(8, 4.5))
keys = [k for k in sorted(med, key=lambda k: (k[4], k[1], k[2], k[3])) if k[0] == "strong" and k[3] > 1]
plt.bar(range(len(keys)), [100 * med[k]["comm"] / med[k]["t"] for k in keys],
        color=["C0" if k[1] == "node" else "C1" for k in keys])
plt.xticks(range(len(keys)), [f"{k[2][0]}{k[3]} {k[1]} N{k[4]}" for k in keys], rotation=90, fontsize=6)
plt.ylabel("time in the halo exchange (%)")
plt.title("Communication share (s = strips, b = blocks; blue = map-by node, orange = map-by slot)")
plt.tight_layout(); plt.savefig("results/comm_share.png", dpi=150); plt.close()

weak = sorted(k for k in med if k[0] == "weak")
if len({k[3] for k in weak}) > 1:
    plt.figure(figsize=(6, 4.5))
    for decomp, sty in (("strips", "o-"), ("blocks", "s-")):
        ks = sorted((k for k in weak if k[2] == decomp), key=lambda k: k[3])
        plt.plot([k[3] for k in ks], [med[k]["t"] for k in ks], sty, label=f"{decomp} (measured)")
        plt.plot([k[3] for k in ks], [model_step(decomp, k[3], k[4], k[1]) * med[k]["steps"] for k in ks], ":", label=f"{decomp} (model)")
    plt.yscale("log")
    plt.xlabel("P (N grows so that each process keeps about 1024 x 1024 nodes)")
    plt.ylabel("run time for 500 steps (s)"); plt.title("Weak scaling (ideal: flat)"); plt.grid(alpha=0.3); plt.legend()
    plt.tight_layout(); plt.savefig("results/weak_scaling.png", dpi=150); plt.close()
print("\nsaved results/perf_summary.csv and the plots in results/")
