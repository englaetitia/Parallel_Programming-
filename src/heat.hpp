// heat.hpp - shared definitions for the 2D heat solver (serial, strips, blocks).
//
// Problem: du/dt = d2u/dx2 + d2u/dy2 on the unit square, alpha = 1,
// N x N intervals, h = 1/N, nodes 0 <= i, j <= N (i along x, j along y).
// Explicit scheme (background notes, Task 5.2), with r = dt / h^2:
//   u_new(i,j) = u(i,j) + r * ( u(i+1,j) + u(i-1,j) + u(i,j+1) + u(i,j-1) - 4 u(i,j) )
// Stable only if r <= 1/4 (Task 6.3).
#pragma once

#include <cstddef>
#include <string>
#include <vector>

// All the options of the program (see README for their meaning).
struct Params {
    std::string kase = "1";        // "1", "2" or "V"
    int N = 64;                    // number of intervals per direction
    double r = 0.2;                // requested r = dt / h^2
    double T = -1.0;               // final time (if given)
    long steps = -1;               // or a fixed number of steps (if given)
    std::string out;               // output file for the final field ("" = no file)
    std::string decomp = "serial"; // serial, strips or blocks
    bool force_unstable = false;   // ONLY for Task 6.7: allow r > 1/4 on purpose
};

// Position of node (i, j) in a grid stored row after row (row j = line y = y_j, i varies fastest).
// row_len is the number of values in one row (N + 1 for the full grid).
inline std::size_t idx(int i, int j, int row_len)
{
    return static_cast<std::size_t>(j) * static_cast<std::size_t>(row_len) + static_cast<std::size_t>(i);
}

// Value of node (i, j) at t = 0 for a test case: interior initial value, or the fixed boundary value.
double initial_value(const std::string& kase, int i, int j, int N);

// Exact solution of test V at time t (used to measure the error).
double exact_V(int i, int j, int N, double t);

// One explicit time step on the rectangle of nodes j_begin..j_end (rows) x i_begin..i_end (columns),
// all inclusive. 'uo' is the old level, 'un' the new one, both stored with rows of length row_len.
// The SAME function is used by every version, so they all do the same arithmetic in the same order
// (that is what makes the parallel results bit-for-bit identical to the serial ones).
void update_block(const double* uo, double* un, int row_len,
                  int j_begin, int j_end, int i_begin, int i_end, double r);

// Result of a run: the final field (full grid, only on rank 0 for parallel runs) and timings in seconds.
struct Result {
    std::vector<double> u;
    double t_comp = 0.0;
    double t_comm = 0.0;
    double t_total = 0.0;
};

// The serial solver (src/serial.cpp).
Result run_serial(const Params& p, long steps, double r);
