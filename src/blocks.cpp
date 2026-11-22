// blocks.cpp - parallel version 2: the plate is cut into a Px x Py grid of rectangles ("blocks").
//
// MPI_Dims_create chooses Px x Py (as square as possible), MPI_Cart_create builds the process grid,
// MPI_Cart_shift gives the 4 neighbours (MPI_PROC_NULL on the outside edges).
// Each process owns nx x ny interior nodes plus a frame of ghost nodes (1 node wide) around them.
// Each step: 4 exchanges. Rows (up/down) are contiguous in memory; columns (left/right) are not, so we
// describe a column with MPI_Type_vector (ny values, 1 at a time, every row_len values) — no copying by hand.
#ifdef USE_MPI
#include "heat.hpp"

#include <mpi.h>
#include <utility>

Result run_blocks(const Params& p, long steps, double r)
{
    int P = 1;
    MPI_Comm_size(MPI_COMM_WORLD, &P);
    const int N = p.N;

    // 1. Process grid. Dimension 0 = x (columns i), dimension 1 = y (rows j). Not periodic.
    int dims[2] = {0, 0}, periods[2] = {0, 0};
    MPI_Dims_create(P, 2, dims);
    MPI_Comm cart;
    MPI_Cart_create(MPI_COMM_WORLD, 2, dims, periods, 0, &cart);
    int rank = 0, coords[2];
    MPI_Comm_rank(cart, &rank);
    MPI_Cart_coords(cart, rank, 2, coords);
    int left, right, down, up;
    MPI_Cart_shift(cart, 0, 1, &left, &right);
    MPI_Cart_shift(cart, 1, 1, &down, &up);

    // 2. My interior nodes: columns i0 .. i0+nx-1 and rows j0 .. j0+ny-1.
    int fi, nx, fj, ny;
    split(N - 1, dims[0], coords[0], fi, nx);
    split(N - 1, dims[1], coords[1], fj, ny);
    const int i0 = 1 + fi, j0 = 1 + fj;
    const int RL = nx + 2;                                 // local row length (with the 2 ghost columns)

    // Local node (a, b) = global node (i0 + a - 1, j0 + b - 1), a = 0 .. nx+1, b = 0 .. ny+1.
    // Ghosts on the outside of the plate hold the boundary values (never change); the others are refreshed every step.
    std::vector<double> u_old(static_cast<std::size_t>(ny + 2) * RL), u_new(u_old.size());
    for (int b = 0; b <= ny + 1; ++b)
        for (int a = 0; a <= nx + 1; ++a)
            u_old[idx(a, b, RL)] = u_new[idx(a, b, RL)] = initial_value(p.kase, i0 + a - 1, j0 + b - 1, N);

    MPI_Datatype column;                                   // ny values, one per local row
    MPI_Type_vector(ny, 1, RL, MPI_DOUBLE, &column);
    MPI_Type_commit(&column);

    // 3. Time loop
    Result res;
    MPI_Barrier(cart);
    const double t0 = MPI_Wtime();
    for (long s = 0; s < steps; ++s) {
        double* u = u_old.data();
        const double c0 = MPI_Wtime();
        // up / down: rows of nx interior values (contiguous)
        MPI_Sendrecv(u + idx(1, ny, RL), nx, MPI_DOUBLE, up, 0,
                     u + idx(1, 0, RL), nx, MPI_DOUBLE, down, 0, cart, MPI_STATUS_IGNORE);
        MPI_Sendrecv(u + idx(1, 1, RL), nx, MPI_DOUBLE, down, 1,
                     u + idx(1, ny + 1, RL), nx, MPI_DOUBLE, up, 1, cart, MPI_STATUS_IGNORE);
        // left / right: columns of ny interior values (one 'column' each)
        MPI_Sendrecv(u + idx(nx, 1, RL), 1, column, right, 2,
                     u + idx(0, 1, RL), 1, column, left, 2, cart, MPI_STATUS_IGNORE);
        MPI_Sendrecv(u + idx(1, 1, RL), 1, column, left, 3,
                     u + idx(nx + 1, 1, RL), 1, column, right, 3, cart, MPI_STATUS_IGNORE);
        const double c1 = MPI_Wtime();
        update_block(u_old.data(), u_new.data(), RL, 1, ny, 1, nx, r);    // same kernel as the serial version
        const double c2 = MPI_Wtime();
        res.t_comm += c1 - c0;
        res.t_comp += c2 - c1;
        std::swap(u_old, u_new);
    }
    res.t_total = MPI_Wtime() - t0;
    MPI_Type_free(&column);

    // 4. Collect on rank 0: everyone packs its nx*ny interior values (row by row) and sends them;
    //    rank 0 knows where each block goes from that process's coordinates.
    //    Only when it is needed (output file or case V) — see strips.cpp.
    const bool need_field = !p.out.empty() || p.kase == "V";
    if (need_field) {
        std::vector<double> mine(static_cast<std::size_t>(nx) * ny);
        for (int b = 1; b <= ny; ++b)
            for (int a = 1; a <= nx; ++a)
                mine[static_cast<std::size_t>(b - 1) * nx + (a - 1)] = u_old[idx(a, b, RL)];

        std::vector<int> counts(P), displs(P), qfi(P), qnx(P), qfj(P), qny(P);
        int total = 0;
        for (int q = 0; q < P; ++q) {
            int c[2];
            MPI_Cart_coords(cart, q, 2, c);
            split(N - 1, dims[0], c[0], qfi[q], qnx[q]);
            split(N - 1, dims[1], c[1], qfj[q], qny[q]);
            counts[q] = qnx[q] * qny[q];
            displs[q] = total;
            total += counts[q];
        }
        std::vector<double> all(rank == 0 ? total : 0);
        MPI_Gatherv(mine.data(), nx * ny, MPI_DOUBLE, rank == 0 ? all.data() : nullptr,
                    counts.data(), displs.data(), MPI_DOUBLE, 0, cart);

        if (rank == 0) {
            const int L = N + 1;
            res.u.assign(static_cast<std::size_t>(L) * L, 0.0);
            for (int j = 0; j <= N; ++j)                       // start with the boundary values everywhere
                for (int i = 0; i <= N; ++i)
                    res.u[idx(i, j, L)] = initial_value(p.kase, i, j, N);
            for (int q = 0; q < P; ++q)                        // then paste each block at its place
                for (int b = 0; b < qny[q]; ++b)
                    for (int a = 0; a < qnx[q]; ++a)
                        res.u[idx(1 + qfi[q] + a, 1 + qfj[q] + b, L)] =
                            all[static_cast<std::size_t>(displs[q]) + static_cast<std::size_t>(b) * qnx[q] + a];
        }
    }

    // 5. Report the slowest process.
    double t[3] = {res.t_total, res.t_comp, res.t_comm}, worst[3];
    MPI_Reduce(t, worst, 3, MPI_DOUBLE, MPI_MAX, 0, cart);
    res.t_total = worst[0]; res.t_comp = worst[1]; res.t_comm = worst[2];
    res.layout = std::to_string(dims[0]) + "x" + std::to_string(dims[1]);
    MPI_Comm_free(&cart);
    return res;
}
#endif
