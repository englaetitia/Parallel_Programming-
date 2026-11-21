// main.cpp - the 'heat' program: reads the options, checks stability, runs the chosen version,
// writes the field file and prints one summary line (key=value).
//
// Examples:
//   ./build/heat --case V --N 64 --r 0.2 --T 0.05
//   ./build/heat --case 2 --N 512 --r 0.24 --steps 500 --out u.bin
//   mpirun -np 4 ./build/heat --decomp blocks --case 2 --N 512 --r 0.24 --steps 500 --out u4.bin
#include "heat.hpp"

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <string>

#ifdef USE_MPI
#include <mpi.h>
#endif

static void usage()
{
    std::fprintf(stderr,
        "usage: heat --case 1|2|V --N <intervals> --r <dt/h^2> (--T <time> | --steps <n>)\n"
        "            [--out <file>] [--decomp serial|strips|blocks] [--force-unstable] [--debug]\n");
}

int main(int argc, char** argv)
{
#ifdef USE_MPI
    MPI_Init(&argc, &argv);
#endif
    int rank = 0, P = 1;
#ifdef USE_MPI
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &P);
#endif
    auto fail = [&](const char* msg) {
        if (rank == 0) { std::fprintf(stderr, "error: %s\n", msg); usage(); }
#ifdef USE_MPI
        MPI_Finalize();
#endif
        std::exit(1);
    };

    // ---- 1. Read the options ------------------------------------------------------------
    Params p;
    for (int a = 1; a < argc; ++a) {
        std::string k = argv[a];
        auto value = [&]() -> std::string {
            if (a + 1 >= argc) fail(("missing value after " + k).c_str());
            return argv[++a];
        };
        if      (k == "--case")   p.kase = value();
        else if (k == "--N")      p.N = std::atoi(value().c_str());
        else if (k == "--r")      p.r = std::atof(value().c_str());
        else if (k == "--T")      p.T = std::atof(value().c_str());
        else if (k == "--steps")  p.steps = std::atol(value().c_str());
        else if (k == "--out")    p.out = value();
        else if (k == "--decomp") p.decomp = value();
        else if (k == "--force-unstable") p.force_unstable = true;
        else if (k == "--debug") p.debug = true;
        else fail(("unknown option " + k).c_str());
    }
    if (p.kase != "1" && p.kase != "2" && p.kase != "V") fail("--case must be 1, 2 or V");
    if (p.N < 2) fail("--N must be at least 2");
    if (p.r <= 0) fail("--r must be positive");
    if ((p.T > 0) == (p.steps > 0)) fail("give exactly one of --T (final time) or --steps (number of steps)");

    // ---- 2. Stability check (Task 6.3: the explicit scheme is stable only if r <= 1/4) ----
    if (p.r > 0.25 && !p.force_unstable) {
        if (rank == 0)
            std::fprintf(stderr,
                "error: r = %g is unstable. The explicit 2D scheme needs r = dt/h^2 <= 1/4 (Task 6.3);\n"
                "       with a larger r, errors grow at every step and the solution blows up.\n", p.r);
#ifdef USE_MPI
        MPI_Finalize();
#endif
        return 1;
    }

    // ---- 3. Time step and number of steps --------------------------------------------------
    const double h = 1.0 / p.N;
    long steps;
    double r;                                   // the r actually used
    if (p.T > 0) {
        // Choose dt so that T/dt is an integer and r is not exceeded: steps = ceil(T / (r h^2)).
        steps = static_cast<long>(std::ceil(p.T / (p.r * h * h) - 1e-9));
        if (steps < 1) steps = 1;
        r = p.T / (steps * h * h);              // dt = T / steps, so r = dt / h^2 <= requested r
    } else {
        steps = p.steps;
        r = p.r;
    }
    const double dt = r * h * h;

    // ---- 4. Run the chosen version ---------------------------------------------------------
    Result res;
    if (p.decomp == "serial") {
        if (P != 1) fail("--decomp serial must run with 1 process");
        res = run_serial(p, steps, r);
    } else if (p.decomp == "strips" || p.decomp == "blocks") {
#ifdef USE_MPI
        // Every process must own at least one interior row (strips) / one row and one column (blocks).
        if (p.decomp == "strips") {
            if (P > p.N - 1) fail("too many processes: strips need P <= N - 1");
            if (p.debug && (p.N > 16 || steps > 3)) fail("--debug is only for tiny runs (N <= 16, at most 3 steps)");
            res = run_strips(p, steps, r);
        } else {
            int dims[2] = {0, 0};
            MPI_Dims_create(P, 2, dims);
            if (dims[0] > p.N - 1 || dims[1] > p.N - 1) fail("too many processes for this N (blocks)");
            res = run_blocks(p, steps, r);
        }
#else
        fail("this program was built without MPI: only --decomp serial is available");
#endif
    } else {
        fail("--decomp must be serial, strips or blocks");
    }

    // ---- 5. Output (rank 0 holds the full field) -------------------------------------------
    if (rank == 0) {
        if (!p.out.empty()) {
            std::ofstream f(p.out, std::ios::binary);
            f.write(reinterpret_cast<const char*>(res.u.data()),
                    static_cast<std::streamsize>(res.u.size() * sizeof(double)));
            if (!f) fail("could not write the output file");
        }
        std::printf("decomp=%s P=%d layout=%s case=%s N=%d steps=%ld r=%.6g dt=%.6e T=%.6g t_total=%.6f t_comp=%.6f t_comm=%.6f",
                    p.decomp.c_str(), P, res.layout.c_str(), p.kase.c_str(), p.N, steps, r, dt, steps * dt,
                    res.t_total, res.t_comp, res.t_comm);
        if (p.kase == "V") {                    // error against the exact solution at the final time
            const int L = p.N + 1;
            const double t = steps * dt;
            double e_inf = 0.0, e_sum2 = 0.0;
            for (int j = 0; j <= p.N; ++j)
                for (int i = 0; i <= p.N; ++i) {
                    const double e = res.u[idx(i, j, L)] - exact_V(i, j, p.N, t);
                    e_inf = std::fmax(e_inf, std::fabs(e));
                    e_sum2 += e * e;
                }
            const double e_l2 = std::sqrt(h * h * e_sum2);     // ||e||_{2,h} = sqrt(dx dy sum e^2)
            std::printf(" err_inf=%.6e err_l2=%.6e", e_inf, e_l2);
        }
        std::printf("\n");
    }

#ifdef USE_MPI
    MPI_Finalize();
#endif
    return 0;
}
