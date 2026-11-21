#!/usr/bin/env python3
"""heatmap.py - draw a field file written by heat --out.

Usage: python3 scripts/heatmap.py u.bin N [picture.png]
The file holds (N+1)x(N+1) little-endian doubles, row j = line y = j/N, i (x) varies fastest.
"""
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

path, N = sys.argv[1], int(sys.argv[2])
png = sys.argv[3] if len(sys.argv) > 3 else path.rsplit(".", 1)[0] + ".png"
u = np.fromfile(path, dtype="<f8")
assert u.size == (N + 1) ** 2, f"file has {u.size} values, expected {(N + 1) ** 2}"
u = u.reshape(N + 1, N + 1)                      # u[j, i]
plt.figure(figsize=(5.5, 4.5))
plt.imshow(u, origin="lower", extent=[0, 1, 0, 1], cmap="inferno")
plt.colorbar(label="temperature u")
plt.xlabel("x"); plt.ylabel("y"); plt.title(path)
plt.tight_layout()
plt.savefig(png, dpi=150)
print(f"saved {png}  (min {u.min():.4g}, max {u.max():.4g})")
