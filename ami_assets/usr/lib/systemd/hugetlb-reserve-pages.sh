#!/bin/sh
#
# Reserve hugepages when NUMA-aware.
# Always reserve pages only on the first NUMA node.
#
# N.B. This currently only supports one or two NUMA nodes as it does not
# NUMA nodes aren't guaranteed to be numbered contiguously and fully parsing
# /sys/devices/system/node/online is non-trivial.
#
# NUMPAGES should be replaced with the required number of pages before use.
nodes_path=h
if [ ! -d $nodes_path ]; then
	echo "ERROR: $nodes_path does not exist"
	exit 1
fi

reserve_pages()
{
	echo "$1" > "$nodes_path/$2/hugepages/hugepages-1048576kB/nr_hugepages"
}

# Get the number of NUMA nodes.
numa_node_count=$(lscpu | grep -F "NUMA node(s)" | awk '{ print $3 }')

reserve_pages NUMPAGES 0
if [ "$numa_node_count" -gt 1 ]; then
    reserve_pages 0 1
fi