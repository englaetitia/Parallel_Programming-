# Parallel 2D Heat Diffusion with MPI over Tailscale

Course project — Parallel Programming (ESIB, Maroun Chamoun).

**Team:** Laetitia Daou · Georges-Anthony El Hajj

We build a small MPI cluster from our own machines (Ubuntu 24.04 VMs joined with Tailscale)
and solve the 2D heat equation on the unit square with an explicit finite-difference scheme,
in three versions: serial, 1D strips and 2D blocks.

## Repository layout

| Path            | Content                                                           |
| --------------- | ----------------------------------------------------------------- |
| `src/`          | The `heat` solver (serial, strips, blocks)                        |
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
./build/heat --case V --N 64 --r 0.2 --T 0.05                  # test V, prints err_inf and err_l2
./build/heat --case 2 --N 512 --r 0.24 --steps 500 --out u.bin # case 2, saves the field
python3 scripts/heatmap.py u.bin 512                           # picture of the field -> u.png
python3 scripts/convergence.py                                 # convergence study (Task 7.2)

# parallel, on one VM (more processes than cores needs --oversubscribe):
mpirun --oversubscribe -np 4 ./build/heat --decomp strips --case 2 --N 512 --r 0.24 --steps 500 --out s.bin
cmp u.bin s.bin && echo identical
# parallel, on the cluster (both VMs, hostfile 'hosts', Tailscale interface):
bash scripts/run_mpi.sh -np 4 ./build/heat --decomp blocks --case 2 --N 2048 --r 0.24 --steps 500
```

Options:

| Option             | Meaning                                                   | Example                      |
| ------------------ | --------------------------------------------------------- | ---------------------------- |
| `--case`           | 1, 2 or V                                                 | `--case 2`                   |
| `--N`              | intervals per direction                                   | `--N 1024`                   |
| `--r`              | Δt / h² (must be ≤ 1/4)                                   | `--r 0.2`                    |
| `--T` / `--steps`  | final time or number of steps (exactly one of them)       | `--steps 500`                |
| `--out`            | output field file                                         | `--out u.bin`                |
| `--decomp`         | serial (1 process), strips or blocks                      | `--decomp blocks`            |
| `--force-unstable` | allow r > 1/4, **only** for Task 6.7                      | `--r 0.2625 --force-unstable`|
| `--debug`          | strips, tiny runs only: print every local array with ghost rows | `--N 8 --steps 1 --debug` |

With `--T`, the program uses `steps = ceil(T / (r h²))` and `dt = T / steps`, so `T/dt` is an integer and the
requested r is never exceeded. With r > 1/4 (and no `--force-unstable`) it refuses to run and explains why.

Output: one summary line `key=value` (decomp, P, layout = process grid Px×Py, case, N, steps, r, dt, T,
t_total, t_comp, t_comm, plus err_inf and err_l2 for case V). Times are for the time-stepping loop only;
for parallel runs, each is the maximum over the processes. With `--out`, the full field as described above.

## Checking and measuring

| Script | What it does |
| ------ | ------------ |
| `scripts/check_identical.sh` | serial vs strips (P = 1–4) and blocks (P = 1–4, 6), cases 1/2/V, N = 64 and 67, compared with `cmp`; a run that fails to start is reported `FAILED`. On the cluster: `MPIRUN="bash scripts/run_mpi.sh --oversubscribe" bash scripts/check_identical.sh` (P = 6 needs more than the 4 slots; correctness only). Output: `results/check_identical_cluster.txt` |
| `scripts/convergence.py` | Task 7.2: test V, N = 16 … 256, r = 0.2, T = 0.05 → table, `results/raw/convergence.csv`, `results/convergence.png` |
| `scripts/heatmap.py` | `python3 scripts/heatmap.py u.bin N [out.png]`: picture of a field file |
| `tools/pingpong.cpp`, `scripts/fit_pingpong.py` | network latency ts and time per byte tw (Part 0): `bash scripts/run_mpi.sh --map-by node -np 2 tools/pingpong [max_bytes]` (build: `mpicxx -O2 -o tools/pingpong tools/pingpong.cpp`) |
| `scripts/perf_baseline.sh` | Part 4 exp. 1: serial, N = 512 … 8192, 500 steps, 3 repeats → `results/raw/baseline_<vm>.txt` |
| `scripts/perf_scaling.sh` | Part 4 exp. 2–3 on the cluster: strong (N = 512, 2048, 8192; P = 1–4; strips and blocks; `--map-by node` and `--map-by slot`) and weak scaling (≈ 1024² nodes per process) → `results/raw/scaling.txt`. Options: `strong`, `weak`, `local` (only the runs that stay on the first VM). Runs already in the file are skipped, so it can be stopped and restarted |
| `scripts/analyze_perf.py` | medians, spread, speed-up, efficiency, communication share and the performance model → `results/perf_summary.csv` and the plots in `results/` |

`results/raw/scaling_partial_22nov.txt` is a backup copy of the first 132 lines of `scaling.txt`, taken before the last runs; `scaling.txt` is the complete file.

**Before every cluster run:** after a `git pull` that changes `src/`, rebuild on **every** VM (`cmake --build build`) and check that
`md5sum build/heat` is identical on all VMs — two different programs deadlock at the end of a run.
