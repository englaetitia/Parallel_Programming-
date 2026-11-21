#!/usr/bin/env bash
# run_mpi.sh - run an MPI program on our Tailscale cluster.
# Usage: bash scripts/run_mpi.sh -np 4 tools/hello_mpi
#
# --hostfile hosts                       : the list of VMs and their slots (file "hosts" at the repo root)
# --mca oob_tcp_if_include tailscale0    : MPI's control messages go through Tailscale
# --mca btl_tcp_if_include tailscale0    : MPI's data messages go through Tailscale
# --mca btl tcp,self                     : use TCP between processes (and "self" for a process talking to itself)
# Without the two "tailscale0" options, MPI may try the VM's private 10.x address, which the other VM can't reach, and hang.

cd "$(dirname "$0")/.." || exit 1
exec mpirun --hostfile hosts \
     --mca oob_tcp_if_include tailscale0 \
     --mca btl_tcp_if_include tailscale0 \
     --mca btl tcp,self \
     "$@"
