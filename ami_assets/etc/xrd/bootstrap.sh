#!/usr/bin/env bash

set -o pipefail
set -o nounset
set -o errexit

HUGEPAGES_GB=${HUGEPAGES_GB:-"3"}
ISOLATED_CORES=${ISOLATED_CORES:-"1-3"}

# Copy the ISOLATED_CPUS into the tuned settings.
sudo sed "s/isolated_cores=/isolated_cores=${ISOLATED_CORES}/" -i /etc/tuned/xrd-eks-node-variables.conf

# Copy HUGEPAGES_GB into the tuned settings and hugetlb service env.
# Get the number of NUMA nodes.
numa_node_count=$(lscpu | grep -F "NUMA node(s)" | awk '{ print $3 }')

# Multiply the requested hugepages by the number of NUMA nodes at boot
# so we're guaranteed a contiguous block of pages on each node.
# Then during early boot the systemd service will unreserve all the
# hugepages from all nodes except the first.
boot_hugepages=$((HUGEPAGES_GB * numa_node_count))

sudo sed "s/hugepages_gb=.*/hugepages_gb=${boot_hugepages}/" -i /etc/tuned/xrd-eks-node-variables.conf
echo "HUGEPAGES_GB=${HUGEPAGES_GB}" | sudo tee /etc/xrd/hugetlb-reserve-env.conf

# Start tuned.
sudo systemctl start tuned

# Let tuned actually start up.
# If this sleep is removed, the next step hangs forever.
sleep 10

# Overwrite the defirqaffinity script (that assigns IRQ affinities)
# with a version that gracefully skips IRQs that can't have affinity
# specified. This is fixed in later versions of tuned but those are not
# easily available on Amazon Linux 2 (and have lots of dependencies that also
# aren't easily available).
sudo cp /etc/tuned/xrd-eks-node/defirqaffinity.py /usr/libexec/tuned/defirqaffinity.py

# Set the tuned profile.
sudo tuned-adm profile xrd-eks-node

# Sanity check the tuned profile is active (mostly for packer logs).
sudo tuned-adm active

# Load the kernel module - need to load uio first.
sudo modprobe uio
sudo modprobe igb_uio wc_activate=1

# Enable and run the hugepage configuration service.
sudo systemctl enable hugetlb-gigantic-pages
sudo systemctl start hugetlb-gigantic-pages
