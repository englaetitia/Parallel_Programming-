#!/usr/bin/env python3
"""analyze_perf.py - Part 4: turn the raw run lines into tables and plots, with the performance model.

Reads results/raw/baseline_*.txt and results/raw/scaling.txt (written by perf_baseline.sh / perf_scaling.sh).
Uses the MEDIAN of the 3 repeats and also prints the spread (max - min) / median.
Writes:
  results/perf_summary.csv       one line per configuration (median times, speed-up, efficiency, comm share)
  results/speedup_N<N>.png       speed-up S(P) = T1/TP, measured (points) and model (dashed), for each N
  results/efficiency_N<N>.png    efficiency E(P) = S(P)/P
  results/comm_share.png         fraction of the time spent in the halo exchange
  results/weak_scaling.png       run time vs P at fixed work per process

Performance model (background notes, Task 8.2), time per step:
  compute  : c * (number of interior nodes per process)        c = seconds per node update (from the baseline)
  strips   : + 2 * (ts + 8 (N+1) tw)                            two rows of N+1 doubles
  blocks   : + 4 * (ts + 8 (N/sqrt(P)) tw)                      four sides of about N/sqrt(P) doubles
  (no communication when P = 1). ts, tw: our ping-pong measurements (Step 5), cross-VM or same-VM
  depending on whether the run uses both VMs.
Usage: python3 scripts/analyze_perf.py [--ts 0.029 --tw 6.7e-6]
"""
import argparse, glob, math, os, statistics as st
from collections import defaultdict
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ap = argparse.ArgumentParser()
ap.add_argument("--ts", type=float, default=29.0e-3, help="cross-VM latency in s (Step 5: 29.0 ms)")
ap.add_argument("--tw", type=float, default=6.7e-6, help="cross-VM time per byte in s (Step 5: 6.7 us/byte)")
ap.add_argument("--ts-local", type=float, default=0.014e-3, help="same-VM latency (Step 5: 0.014 ms)")
ap.add_argument("--tw-local", type=float, default=1 / 2554e6, help="same-VM time per byte (Step 5: 2554 MB/s)")
ap.add_argument("--slots", type=int, default=2, help="processes per VM (hosts file)")
a = ap.parse_args()

def parse(path):
    rows = []
    for line in open(path):
        kv = dict(x.split("=", 1) for x in line.split() if "=" in x)
        if "t_total" in kv:
            rows.append(kv)
    return rows

os.makedirs("results", exist_ok=True)

# ---- 1. Baseline: compute rate c (seconds per node update), per VM and N ----------------------
base = defaultdict(list)
for f in glob.glob("results/raw/baseline_*.txt"):
    for kv in parse(f):
        N, steps = int(kv["N"]), int(kv["steps"])
        base[(kv["vm"], N)].append(float(kv["t_total"]) / (steps * (N - 1) ** 2))
if base:
    print("Baseline (serial): time per node update, median of repeats")
    for (vm, N), v in sorted(base.items()):
        print(f"  {vm:15s} N={N:5d}  {st.median(v)*1e9:7.3f} ns/node   spread {100*(max(v)-min(v))/st.median(v):5.1f}%")
c_all = [st.median(v) for v in base.values()]
c = st.median(c_all) if c_all else 1.75e-9          # fallback: 0.57e9 updates/s measured in Step 7
print(f"compute rate used in the model: c = {c*1e9:.3f} ns per node update\n")

def model(decomp, N, P, spans_vms):
    ts, tw = (a.ts, a.tw) if spans_vms else (a.ts_local, a.tw_local)
    comp = c * (N - 1) ** 2 / P
    if P == 1:
        return comp
    if decomp == "strips":
        return comp + 2 * (ts + 8 * (N + 1) * tw)
    return comp + 4 * (ts + 8 * (N / math.sqrt(P)) * tw)

# ---- 2. Scaling runs ---------------------------------------------------------------------------
if not os.path.exists("results/raw/scaling.txt"):
    print("no results/raw/scaling.txt yet (run scripts/perf_scaling.sh on the cluster)"); raise SystemExit
groups = defaultdict(list)
for kv in parse("results/raw/scaling.txt"):
    key = (kv["exp"], kv["map"], kv["decomp"], int(kv["P"]), int(kv["N"]))
    groups[key].append((float(kv["t_total"]), float(kv["t_comp"]), float(kv["t_comm"]), int(kv["steps"])))

med = {}
for key, runs in groups.items():
    tt = [r[0] for r in runs]
    m = st.median(tt)
    i = tt.index(sorted(tt)[len(tt) // 2])           # the median run, for comp/comm
    med[key] = dict(t=m, comp=runs[i][1], comm=runs[i][2], steps=runs[i][3], n=len(tt),
                    spread=(max(tt) - min(tt)) / m if m else 0.0)

def spans(map_, P):                                  # does this run use both VMs?
    return P > 1 and (map_ == "node" or P > a.slots)

with open("results/perf_summary.csv", "w") as f:
    f.write("exp,map,decomp,P,N,runs,t_median_s,spread_pct,t_per_step_s,speedup,efficiency,comm_share,model_t_per_step_s\n")
    print(f"{'exp':6} {'map':4} {'decomp':6} {'P':>2} {'N':>5} {'t_med(s)':>9} {'spread':>7} {'S(P)':>6} {'E(P)':>5} {'comm%':>6} {'model/step':>11}")
    for key in sorted(med):
        exp, map_, decomp, P, N = key
        m = med[key]
        t1 = med.get((exp, map_, decomp, 1, N), {}).get("t") if exp == "strong" else None
        S = t1 / m["t"] if t1 else float("nan")
        E = S / P if t1 else float("nan")
        share = m["comm"] / m["t"] if m["t"] else 0.0
        mod = model(decomp, N, P, spans(map_, P))
        print(f"{exp:6} {map_:4} {decomp:6} {P:2d} {N:5d} {m['t']:9.3f} {100*m['spread']:6.1f}% {S:6.2f} {E:5.2f} {100*share:5.1f}% {mod*1e3:8.3f} ms")
        f.write(f"{exp},{map_},{decomp},{P},{N},{m['n']},{m['t']},{100*m['spread']:.2f},{m['t']/m['steps']},{S},{E},{share},{mod}\n")

# ---- 3. Plots ---------------------------------------------------------------------------------
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
            m1 = model(decomp, N, 1, False)
            Sm = [m1 / model(decomp, N, P, spans(map_, P)) for P in Ps]
            ym = Sm if what == "speedup" else [s / P for s, P in zip(Sm, Ps)]
            plt.plot(Ps, ym, ":", color=col, alpha=0.7, label=f"model {decomp}, {map_}")
        if what == "speedup":
            plt.plot([1, 4], [1, 4], "k-", lw=0.6, alpha=0.4, label="ideal")
        plt.xlabel("number of processes P"); plt.ylabel("S(P) = T1 / TP" if what == "speedup" else "E(P) = S(P) / P")
        plt.title(f"Strong scaling, N = {N}, 500 steps"); plt.grid(alpha=0.3); plt.legend(fontsize=7)
        plt.tight_layout(); plt.savefig(f"results/{what}_N{N}.png", dpi=150); plt.close()

plt.figure(figsize=(7, 4.5))
labels, shares = [], []
for key in sorted(med):
    if key[0] == "strong" and key[3] > 1:
        labels.append(f"{key[2][0]}{key[3]} {key[1][0]} N{key[4]}")
        shares.append(100 * med[key]["comm"] / med[key]["t"])
plt.bar(range(len(shares)), shares)
plt.xticks(range(len(shares)), labels, rotation=90, fontsize=6)
plt.ylabel("time in halo exchange (%)"); plt.title("Communication share (s = strips, b = blocks; n = node, s = slot)")
plt.tight_layout(); plt.savefig("results/comm_share.png", dpi=150); plt.close()

weak = sorted(k for k in med if k[0] == "weak")
if weak:
    plt.figure(figsize=(6, 4.5))
    for decomp, sty in (("strips", "o-"), ("blocks", "s-")):
        ks = sorted((k for k in weak if k[2] == decomp), key=lambda k: k[3])
        plt.plot([k[3] for k in ks], [med[k]["t"] for k in ks], sty, label=decomp)
    plt.xlabel("P (N grows so that each process keeps about 1024 x 1024 nodes)")
    plt.ylabel("run time for 500 steps (s)"); plt.title("Weak scaling (ideal: flat)"); plt.grid(alpha=0.3); plt.legend()
    plt.tight_layout(); plt.savefig("results/weak_scaling.png", dpi=150); plt.close()
print("\nsaved results/perf_summary.csv and the plots in results/")
