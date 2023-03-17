#!/bin/bash
#
# Reserve hugepages when NUMA-aware.
# Always reserve pages only on the first NUMA node.
#
# N.B. This currently only supports one or two NUMA nodes as
# NUMA nodes aren't guaranteed to be numbered contiguously and fully parsing
# /sys/devices/system/node/online is non-trivial.
#
# This script requires the 'HUGEPAGES_GB' env var to be set to the number
# of 1GiB hugepages required on the first NUMA node.
set -e
set -o pipefail

nodes_path=/sys/devices/system/node/
if [ ! -d "$nodes_path" ]; then
    echo "ERROR: $nodes_path does not exist"
    exit 1
fi

reserve_pages() {
    echo "$1" > "$nodes_path/node$2/hugepages/hugepages-1048576kB/nr_hugepages"
}

# Get the number of NUMA nodes.
numa_node_count=$(lscpu | grep -F "NUMA node(s)" | awk '{ print $3 }')

reserve_pages "$HUGEPAGES_GB" 0
if [ "$numa_node_count" -gt 1 ]; then
    reserve_pages 0 1
fi