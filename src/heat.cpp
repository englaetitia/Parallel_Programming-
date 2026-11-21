// heat.cpp - pieces shared by all versions: initial/boundary values, exact solution, the update kernel.
#include "heat.hpp"

#include <cmath>

double initial_value(const std::string& kase, int i, int j, int N)
{
    const bool left = (i == 0), right = (i == N), bottom = (j == 0), top = (j == N);
    const bool boundary = left || right || bottom || top;

    if (kase == "1") {                       // Case 1: all four edges hot (u = 1), interior cold (0)
        return boundary ? 1.0 : 0.0;
    }
    if (kase == "2") {                       // Case 2: top and bottom hot (corners included), left/right cold
        if (bottom || top) return 1.0;
        return 0.0;                          // left/right edges and interior
    }
    // Case V (verification): u0 = sin(pi x) sin(pi y), u = 0 on all edges
    if (boundary) return 0.0;
    const double pi = 3.14159265358979323846;
    const double h = 1.0 / N;
    return std::sin(pi * i * h) * std::sin(pi * j * h);
}

double exact_V(int i, int j, int N, double t)
{
    const double pi = 3.14159265358979323846;
    const double h = 1.0 / N;
    return std::sin(pi * i * h) * std::sin(pi * j * h) * std::exp(-2.0 * pi * pi * t);
}

void update_block(const double* uo, double* un, int row_len,
                  int j_begin, int j_end, int i_begin, int i_end, double r)
{
    for (int j = j_begin; j <= j_end; ++j) {
        const double* up   = uo + idx(0, j + 1, row_len);   // row above
        const double* mid  = uo + idx(0, j,     row_len);   // this row
        const double* down = uo + idx(0, j - 1, row_len);   // row below
        double* out        = un + idx(0, j,     row_len);
        for (int i = i_begin; i <= i_end; ++i) {
            // Fixed order of operations (never change it in only one version!)
            out[i] = mid[i] + r * ((mid[i + 1] + mid[i - 1]) + (up[i] + down[i]) - 4.0 * mid[i]);
        }
    }
}
