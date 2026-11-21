// hello_mpi.cpp - first MPI test (Step 4).
// Every process prints its rank (its number), the total number of processes,
// and the name of the machine (VM) it is running on.
//
// Build (in each VM, same path):  mpicxx -O2 -o tools/hello_mpi tools/hello_mpi.cpp
// Run on the cluster:              bash scripts/run_mpi.sh -np 4 tools/hello_mpi

#include <mpi.h>
#include <cstdio>

int main(int argc, char** argv)
{
    MPI_Init(&argc, &argv);                    // start MPI (must be the first MPI call)

    int rank = 0, size = 0;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);      // my number: 0 .. size-1
    MPI_Comm_size(MPI_COMM_WORLD, &size);      // how many processes in total

    char host[MPI_MAX_PROCESSOR_NAME];
    int len = 0;
    MPI_Get_processor_name(host, &len);        // name of the VM I run on

    std::printf("Hello from rank %d of %d on %s\n", rank, size, host);

    MPI_Finalize();                            // stop MPI (last MPI call)
    return 0;
}
