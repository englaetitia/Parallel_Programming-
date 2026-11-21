// pingpong.cpp - measure our network (Step 5).
//
// Rank 0 sends a message of m bytes to rank 1, which sends it straight back ("ping-pong").
// We repeat it many times and take the average round-trip time. Half of it is the one-way time t(m).
// Message sizes: 8 bytes, 16, 32, ... up to 16 MB (powers of two).
// From the results we fit the model  t(m) = ts + m * tw :
//   ts = latency (start-up cost of any message, seen with small messages)
//   1/tw = bandwidth (bytes per second, seen with large messages)
//
// Build: mpicxx -O2 -o tools/pingpong tools/pingpong.cpp
// Run (exactly 2 processes), output saved as CSV:
//   same VM   : bash scripts/run_mpi.sh -np 2 --host heat-laetitia:2 tools/pingpong > results/raw/pingpong_laetitia_same.csv
//   two VMs   : bash scripts/run_mpi.sh -np 2 --host heat-laetitia:1,heat-georges:1 tools/pingpong > results/raw/pingpong_laetitia_georges.csv

#include <mpi.h>
#include <cstdio>
#include <vector>

int main(int argc, char** argv)
{
    MPI_Init(&argc, &argv);

    int rank = 0, size = 0;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);
    if (size != 2) {                                   // ping-pong needs exactly two players
        if (rank == 0) std::fprintf(stderr, "pingpong needs exactly 2 processes (use -np 2)\n");
        MPI_Abort(MPI_COMM_WORLD, 1);
    }

    // Collect both host names on rank 0, so the output file says where each rank ran.
    char host[MPI_MAX_PROCESSOR_NAME] = {0};
    int len = 0;
    MPI_Get_processor_name(host, &len);
    char hosts[2][MPI_MAX_PROCESSOR_NAME] = {{0}};
    MPI_Gather(host, MPI_MAX_PROCESSOR_NAME, MPI_CHAR,
               hosts, MPI_MAX_PROCESSOR_NAME, MPI_CHAR, 0, MPI_COMM_WORLD);

    const long max_bytes = 16L * 1024 * 1024;          // 16 MB
    std::vector<char> buf(max_bytes, 'x');             // one buffer, reused for every size
    const int other = 1 - rank;                        // rank 0 talks to 1, rank 1 talks to 0

    if (rank == 0) {
        std::printf("# rank0=%s rank1=%s\n", hosts[0], hosts[1]);
        std::printf("bytes,reps,avg_round_trip_s,one_way_s,bandwidth_MB_per_s\n");
        std::fflush(stdout);
    }

    for (long m = 8; m <= max_bytes; m *= 2) {
        // Fewer repetitions for big messages, so the whole run stays a few minutes on a slow network.
        const int reps = (m <= 64 * 1024) ? 50 : (m <= 1024 * 1024 ? 10 : 3);
        const int count = static_cast<int>(m);

        // One untimed exchange first ("warm-up"): the first message also sets up the connection.
        if (rank == 0) {
            MPI_Send(buf.data(), count, MPI_CHAR, other, 0, MPI_COMM_WORLD);
            MPI_Recv(buf.data(), count, MPI_CHAR, other, 0, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
        } else {
            MPI_Recv(buf.data(), count, MPI_CHAR, other, 0, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
            MPI_Send(buf.data(), count, MPI_CHAR, other, 0, MPI_COMM_WORLD);
        }

        MPI_Barrier(MPI_COMM_WORLD);                   // both start timing together
        const double t0 = MPI_Wtime();
        for (int r = 0; r < reps; ++r) {
            if (rank == 0) {                           // ping ...
                MPI_Send(buf.data(), count, MPI_CHAR, other, 0, MPI_COMM_WORLD);
                MPI_Recv(buf.data(), count, MPI_CHAR, other, 0, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
            } else {                                   // ... pong
                MPI_Recv(buf.data(), count, MPI_CHAR, other, 0, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
                MPI_Send(buf.data(), count, MPI_CHAR, other, 0, MPI_COMM_WORLD);
            }
        }
        const double elapsed = MPI_Wtime() - t0;

        if (rank == 0) {
            const double rtt = elapsed / reps;         // average round trip
            const double one_way = rtt / 2.0;          // t(m) in the model
            const double mbps = (m / one_way) / 1e6;   // MB per second (1 MB = 10^6 bytes)
            std::printf("%ld,%d,%.9e,%.9e,%.3f\n", m, reps, rtt, one_way, mbps);
            std::fflush(stdout);                       // show each line as soon as it is measured
        }
    }

    MPI_Finalize();
    return 0;
}
