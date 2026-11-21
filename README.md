# Parallel 2D Heat Diffusion with MPI over Tailscale

Course project — Parallel Programming (ESIB, Maroun Chamoun).

**Team:** Laetitia Daou · Georges-Anthony El Hajj

We build a small MPI cluster from our own machines (Ubuntu 24.04 VMs joined with Tailscale)
and solve the 2D heat equation on the unit square with an explicit finite-difference scheme,
in three versions: serial, 1D strips and 2D blocks.

## Repository layout

| Path            | Content                                                           |
| --------------- | ----------------------------------------------------------------- |
| `src/`          | The `heat` solver (serial, strips, blocks; optional CUDA)         |
| `tools/`        | `hello_mpi.cpp`, `pingpong.cpp`                                   |
| `scripts/`      | Run scripts, output comparison script, plotting scripts           |
| `results/raw/`  | Raw outputs of every run (never deleted)                          |
| `tasks/`        | Solutions to the background-notes Tasks                           |
| `report/`       | Report sources and figures                                        |
| `hosts.example` | Example MPI hostfile                                              |
| `llm_log/`      | Complete log of every AI/LLM interaction (required by the course) |

## Conventions

- Grid: N × N intervals, h = 1/N, nodes 0 ≤ i, j ≤ N, stored in one contiguous array.
- Index: `idx(i, j) = j * (N + 1) + i` — row j is the line y = y_j, i varies fastest; row 0 is y = 0 (bottom).
- Output file: (N+1)×(N+1) raw little-endian doubles, row-major, no header.
- Compile flags: `-O2 -ffp-contract=off`.

## Build

In each VM, from the repository root (one command after the first configure):

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build
```

This produces `build/heat`. Flags: C++17, `-O2 -ffp-contract=off` (identical floating-point results on every machine).
If MPI is not installed, only the serial version is built (with a warning).

## Run

```bash
./build/heat --case V --N 64 --r 0.2 --T 0.05                 # test V, prints err_inf and err_l2
./build/heat --case 2 --N 512 --r 0.24 --steps 500 --out u.bin  # case 2, saves the field
python3 scripts/heatmap.py u.bin 512                          # picture of the field -> u.png
python3 scripts/convergence.py                                # convergence study (Task 7.2)
```

Options:

| Option            | Meaning                       | Example           |
| ----------------- | ----------------------------- | ----------------- |
| `--case`          | 1, 2 or V                     | `--case 2`        |
| `--N`             | intervals per direction       | `--N 1024`        |
| `--r`             | α Δt / h² (must be ≤ 1/4)     | `--r 0.2`         |
| `--T` / `--steps` | final time or number of steps | `--steps 500`     |
| `--out`           | output field file             | `--out u.bin`     |
| `--decomp`        | serial, strips or blocks      | `--decomp blocks` |

Cluster run (from any VM):

```bash
mpirun --hostfile hosts -np 4 \
  --mca oob_tcp_if_include tailscale0 --mca btl_tcp_if_include tailscale0 \
  --mca btl tcp,self ./heat --decomp strips --case 2 --N 1024 --r 0.24 --steps 500
```
