// strips.cpp - parallel version 1: the plate is cut into horizontal bands ("strips") of whole rows.
//
//   rank P-1  | rows ...      |   Each process owns n consecutive interior rows (j0 .. j0+n-1)
//   ...       |---------------|   plus 2 "ghost" rows: a copy of the last row of the process below
//   rank 1    | rows ...      |   (local row 0) and of the first row of the process above (local row n+1).
//   rank 0    | rows 1 ..     |   Before every step, neighbours swap their edge rows (2 x MPI_Sendrecv).
//
// The bottom process has no neighbour below (MPI_PROC_NULL): its ghost row 0 is the real boundary row j = 0,
// which never changes. Same for the top process and j = N. MPI_Sendrecv with MPI_PROC_NULL does nothing.
#ifdef USE_MPI
#include "heat.hpp"

#include <mpi.h>
#include <cstdio>
#include <utility>

// --debug: every rank, in turn, prints its local array, top row first (like the picture), ghost rows marked.
static void print_local(const std::vector<double>& u, int n, int L, int j0, int rank, int P, long step)
{
    for (int q = P - 1; q >= 0; --q) {            // top strip first
        MPI_Barrier(MPI_COMM_WORLD);
        if (q != rank) continue;
        std::printf("--- step %ld, after the exchange: rank %d owns global rows %d..%d ---\n", step, rank, j0, j0 + n - 1);
        for (int k = n + 1; k >= 0; --k) {
            const bool ghost = (k == 0 || k == n + 1);
            std::printf("%s k=%2d (j=%2d):", ghost ? "ghost" : "own  ", k, j0 + k - 1);
            for (int i = 0; i < L; ++i) std::printf(" %.4f", u[idx(i, k, L)]);
            std::printf("\n");
        }
        std::fflush(stdout);
    }
    MPI_Barrier(MPI_COMM_WORLD);
}

Result run_strips(const Params& p, long steps, double r)
{
    int rank = 0, P = 1;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &P);
    const int N = p.N;
    const int L = N + 1;                                   // a row has N+1 values (boundary columns included)

    // 1. Which interior rows (1 .. N-1) are mine?
    int first = 0, n = 0;
    split(N - 1, P, rank, first, n);
    const int j0 = 1 + first;                              // global row number of my local row 1
    const int down = (rank == 0)     ? MPI_PROC_NULL : rank - 1;
    const int up   = (rank == P - 1) ? MPI_PROC_NULL : rank + 1;

    // 2. Local arrays: n real rows + 2 ghost rows. Local row k = global row j0 + k - 1.
    std::vector<double> u_old(static_cast<std::size_t>(n + 2) * L), u_new(u_old.size());
    for (int k = 0; k <= n + 1; ++k)
        for (int i = 0; i <= N; ++i)
            u_old[idx(i, k, L)] = u_new[idx(i, k, L)] = initial_value(p.kase, i, j0 + k - 1, N);

    // 3. Time loop
    Result res;
    MPI_Barrier(MPI_COMM_WORLD);                           // everybody starts the clock together
    const double t0 = MPI_Wtime();
    for (long s = 0; s < steps; ++s) {
        const double c0 = MPI_Wtime();
        // send my top real row (k = n) up, receive my bottom ghost row (k = 0) from below
        MPI_Sendrecv(&u_old[idx(0, n, L)], L, MPI_DOUBLE, up, 0,
                     &u_old[idx(0, 0, L)], L, MPI_DOUBLE, down, 0, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
        // send my bottom real row (k = 1) down, receive my top ghost row (k = n+1) from above
        MPI_Sendrecv(&u_old[idx(0, 1, L)], L, MPI_DOUBLE, down, 1,
                     &u_old[idx(0, n + 1, L)], L, MPI_DOUBLE, up, 1, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
        const double c1 = MPI_Wtime();
        if (p.debug) print_local(u_old, n, L, j0, rank, P, s);
        update_block(u_old.data(), u_new.data(), L, 1, n, 1, N - 1, r);   // same kernel as the serial version
        const double c2 = MPI_Wtime();
        res.t_comm += c1 - c0;
        res.t_comp += c2 - c1;
        std::swap(u_old, u_new);
    }
    res.t_total = MPI_Wtime() - t0;

    // 4. Collect the field on rank 0 (MPI_Gatherv: every process sends a different number of rows).
    std::vector<int> counts(P), displs(P);
    for (int q = 0; q < P; ++q) {
        int f, c;
        split(N - 1, P, q, f, c);
        counts[q] = c * L;                                 // number of doubles sent by process q
        displs[q] = f * L;                                 // where they go, counted from global row 1
    }
    if (rank == 0) {
        res.u.assign(static_cast<std::size_t>(L) * L, 0.0);
        for (int i = 0; i <= N; ++i) {                     // boundary rows j = 0 and j = N
            res.u[idx(i, 0, L)] = initial_value(p.kase, i, 0, N);
            res.u[idx(i, N, L)] = initial_value(p.kase, i, N, N);
        }
    }
    MPI_Gatherv(&u_old[idx(0, 1, L)], n * L, MPI_DOUBLE,
                rank == 0 ? &res.u[idx(0, 1, L)] : nullptr, counts.data(), displs.data(), MPI_DOUBLE,
                0, MPI_COMM_WORLD);

    // 5. Report the slowest process (the one everybody waits for).
    double mine[3] = {res.t_total, res.t_comp, res.t_comm}, worst[3];
    MPI_Reduce(mine, worst, 3, MPI_DOUBLE, MPI_MAX, 0, MPI_COMM_WORLD);
    res.t_total = worst[0]; res.t_comp = worst[1]; res.t_comm = worst[2];
    res.layout = "1x" + std::to_string(P);
    return res;
}
#endif
