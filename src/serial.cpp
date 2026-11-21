// serial.cpp - the reference version: the whole grid on one process.
#include "heat.hpp"

#include <chrono>
#include <utility>

Result run_serial(const Params& p, long steps, double r)
{
    const int N = p.N;
    const int L = N + 1;                                     // values per row
    std::vector<double> u_old(static_cast<std::size_t>(L) * L);
    std::vector<double> u_new(u_old.size());

    // Initial condition + boundary values, in BOTH arrays (boundary nodes are never updated,
    // so they must already be correct in the array we write into).
    for (int j = 0; j <= N; ++j)
        for (int i = 0; i <= N; ++i)
            u_old[idx(i, j, L)] = u_new[idx(i, j, L)] = initial_value(p.kase, i, j, N);

    Result res;
    const auto t0 = std::chrono::steady_clock::now();        // time the stepping loop only
    for (long n = 0; n < steps; ++n) {
        update_block(u_old.data(), u_new.data(), L, 1, N - 1, 1, N - 1, r);   // all interior nodes
        std::swap(u_old, u_new);                             // swap, don't copy (notes, Section 8.2)
    }
    const auto t1 = std::chrono::steady_clock::now();
    res.t_comp = std::chrono::duration<double>(t1 - t0).count();
    res.t_total = res.t_comp;
    res.u = std::move(u_old);                                // after the last swap, u_old holds level 'steps'
    return res;
}
