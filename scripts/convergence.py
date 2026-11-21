#!/usr/bin/env python3
"""convergence.py - convergence study of Task 7.2 (Step 7).

Runs test V to T = 0.05 for N = 16, 32, 64, 128, 256 with the same r, collects the errors,
prints the table of Task 7.2 (with the observed order p_obs = log2(E(h)/E(h/2))),
saves results/raw/convergence.csv and the log-log plot results/convergence.png.

Usage (from the repository root, after building):  python3 scripts/convergence.py [r]
"""
import math, os, subprocess, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

r = sys.argv[1] if len(sys.argv) > 1 else "0.2"     # r = 0.2 gives an exact integer number of steps
T = "0.05"
rows = []
for N in [16, 32, 64, 128, 256]:
    cmd = ["./build/heat", "--case", "V", "--N", str(N), "--r", r, "--T", T]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip()
    kv = dict(item.split("=", 1) for item in out.split())
    rows.append((N, 1.0 / N, int(kv["steps"]), float(kv["err_inf"]), float(kv["err_l2"]), kv["r"]))
    print(out)

os.makedirs("results/raw", exist_ok=True)
print()
print(f"{'N':>5} {'h':>10} {'steps':>7} {'err_inf':>12} {'err_2h':>12} {'p_obs(2,h)':>10}")
with open("results/raw/convergence.csv", "w") as f:
    f.write("N,h,steps,err_inf,err_l2,p_obs_l2,r_used\n")
    for k, (N, h, steps, einf, el2, ru) in enumerate(rows):
        p = "" if k == 0 else f"{math.log2(rows[k-1][4] / el2):.3f}"
        print(f"{N:>5} {h:>10.5f} {steps:>7} {einf:>12.4e} {el2:>12.4e} {p if p else '—':>10}")
        f.write(f"{N},{h},{steps},{einf},{el2},{p},{ru}\n")

hs = [row[1] for row in rows]
plt.figure(figsize=(6, 4.5))
plt.loglog(hs, [row[4] for row in rows], "o-", label="||e||_2,h")
plt.loglog(hs, [row[3] for row in rows], "s-", label="||e||_inf")
c = rows[0][4] / hs[0] ** 2
plt.loglog(hs, [c * h * h for h in hs], "k--", label="slope 2 (reference)")
plt.xlabel("h = 1/N")
plt.ylabel("error at T = 0.05")
plt.title(f"Convergence study, test V (r = {r})")
plt.grid(True, which="both", alpha=0.3)
plt.legend()
plt.tight_layout()
plt.savefig("results/convergence.png", dpi=150)
print("\nsaved results/raw/convergence.csv and results/convergence.png")
