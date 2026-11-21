#!/usr/bin/env python3
"""fit_pingpong.py - fit t(m) = ts + m*tw to ping-pong results (Step 5).

Usage:  python3 scripts/fit_pingpong.py results/raw/pingpong_*.csv
Prints one line per file (latency ts, bandwidth 1/tw) and saves results/pingpong.png.

How the fit works (simple version of what the project sheet asks):
  * ts (latency)   = the one-way time of the smallest message (8 bytes): almost pure start-up cost.
  * tw             = slope of a straight line through the large messages (>= 1 MB), where the
                     size dominates; bandwidth = 1/tw.
  * We also give a least-squares fit over ALL points, for comparison.
"""
import sys, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def load(path):
    hosts = ""
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                hosts = line.lstrip("# ")
                continue
            if line.startswith("bytes"):
                continue
            parts = line.split(",")
            if len(parts) != 5:          # not a data line (e.g. an mpirun error message): skip it
                continue
            try:
                b, one = float(parts[0]), float(parts[3])
            except ValueError:
                continue
            rows.append((b, one))
    if not rows:
        return hosts, None, None
    a = np.array(rows)
    return hosts, a[:, 0], a[:, 1]


def main(files):
    if not files:
        print(__doc__)
        return 1
    print(f"{'file':40s} {'ts (small msg)':>15s} {'bandwidth (big msgs)':>21s} {'ts (fit all)':>13s} {'bw (fit all)':>13s}")
    plt.figure(figsize=(7, 5))
    for path in files:
        hosts, m, t = load(path)
        if m is None or len(m) < 2:
            print(f"{os.path.basename(path):40s} (no measurements in this file: did the run fail? skipped)")
            continue
        ts_small = t[0]
        big = m >= 1024 * 1024
        if big.sum() >= 2:
            tw_big, _ = np.polyfit(m[big], t[big], 1)
        else:
            tw_big = t[-1] / m[-1]
        tw_all, ts_all = np.polyfit(m, t, 1)
        name = os.path.basename(path)
        print(f"{name:40s} {ts_small*1e3:12.3f} ms {1/tw_big/1e6:15.2f} MB/s {ts_all*1e3:10.3f} ms {1/tw_all/1e6:10.2f} MB/s")
        line, = plt.loglog(m, t, "o", label=f"{name} ({hosts})")
        mm = np.logspace(np.log10(m[0]), np.log10(m[-1]), 100)
        plt.loglog(mm, ts_small + mm * tw_big, "-", color=line.get_color(), alpha=0.6)
    plt.xlabel("message size m (bytes)")
    plt.ylabel("one-way time t(m) (s)")
    plt.title("Ping-pong: measured (dots) and model ts + m*tw (lines)")
    plt.grid(True, which="both", alpha=0.3)
    plt.legend(fontsize=7)
    os.makedirs("results", exist_ok=True)
    plt.tight_layout()
    plt.savefig("results/pingpong.png", dpi=150)
    print("plot saved to results/pingpong.png")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
