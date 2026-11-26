#!/usr/bin/env bash
# run_mpi.sh - run an MPI program on our Tailscale cluster.
# Usage: bash scripts/run_mpi.sh -np 4 tools/hello_mpi
#
# --hostfile hosts                       : the list of VMs and their slots (file "hosts" at the repo root)
# --mca oob_tcp_if_include tailscale0    : MPI's control messages go through Tailscale
# --mca btl_tcp_if_include tailscale0    : MPI's data messages go through Tailscale
# --mca btl tcp,self                     : use TCP between processes (and "self" for a process talking to itself)
# Without the two "tailscale0" options, MPI may try the VM's private 10.x address, which the other VM can't reach, and hang.

# MPI_IFACE: the network to use (default tailscale0). On a cable/switch network give the subnet, e.g. MPI_IFACE=192.168.50.0/24
# (a subnet works even if the card has a different name on each VM).
IFACE="${MPI_IFACE:-tailscale0}"
cd "$(dirname "$0")/.." || exit 1
exec mpirun --hostfile hosts \
     --mca oob_tcp_if_include "$IFACE" \
     --mca btl_tcp_if_include "$IFACE" \
     --mca btl tcp,self \
     "$@"
