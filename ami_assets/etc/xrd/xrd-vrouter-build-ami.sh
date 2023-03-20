#!/usr/bin/env bash

set -o pipefail
set -o nounset
set -o errexit

# Location to retrieve the XRd ami_assets.
# The XRd S3 parameters should be set in calling environment.
AMI_ASSETS_URL=${AMI_ASSETS_URL:-"https://${XRD_S3_BUCKET_NAME}.s3.${XRD_S3_BUCKET_REGION}.amazonaws.com/${XRD_S3_KEY_PREFIX}ami_assets"}


# Additional Packages required for XRd vRouter to run
REQUIRED_PACKAGES="""
tuned
tuned-profiles-realtime
tuned-profiles-nfv-guest
"""

# Additional packages required to build DPDK
DPDK_BUILD_PACKAGES="""
kernel-devel-$(uname -r)
numactl-devel
"""

# Additional package group required to build DPDK
DPDK_BUILD_GROUP="Development Tools"

# The ami_assets to retrieve from the S3 bucket
AMI_ASSETS="""
/etc/xrd/bootstrap.sh
/etc/xrd/hugetlb-reserve-pages.sh
/etc/modprobe.d/vfio.conf
/etc/modprobe.d/igb_uio.conf
/etc/modules-load.d/vfio-pci.conf
/etc/modules-load.d/uio.conf
/etc/modules-load.d/igb_uio.conf
/etc/tuned/xrd-eks-node-variables.conf
/etc/tuned/xrd-eks-node/defirqaffinity.py
/etc/tuned/xrd-eks-node/tuned.conf
/usr/lib/systemd/system/hugetlb-gigantic-pages.service
"""

DPDK_SRC=${DPDK_SRC:-"https://fast.dpdk.org/rel/dpdk-19.11.12.tar.xz"}
DPDK_DIR=${DPDK_DIR:-"dpdk-stable-19.11.12"}

install_packages() {
    # Want whitespace splitting here for multiple packages.
    # shellcheck disable=SC2086
    sudo yum install -y $REQUIRED_PACKAGES
}


install_artifact() {
    local ARTIFACT=$1
    local DIR
    DIR=$(dirname "$ARTIFACT")

    sudo mkdir -p "$DIR"
    sudo wget -P "$DIR" "${AMI_ASSETS_URL}${ARTIFACT}"
}


install_ami_assets() {
    local ARTIFACT
    for ARTIFACT in $AMI_ASSETS; do
        install_artifact "$ARTIFACT"
    done
}

build_igb_uio() {
    local DPDK_FILE

    DPDK_FILE=$(basename "$DPDK_SRC")

    # Want whitespace splitting here for multiple packages.
    # shellcheck disable=SC2086
    sudo yum install -y $DPDK_BUILD_PACKAGES
    sudo yum groupinstall -y "$DPDK_BUILD_GROUP"

    wget "$DPDK_SRC"
    tar xf "$DPDK_FILE"
    cd "$DPDK_DIR"

    make config T=x86_64-native-linux-gcc
    make -j4

    sudo cp build/kmod/igb_uio.ko /lib/modules/"$(uname -r)"/kernel/drivers/uio
    sudo depmod -a

    cd ..

    # Clean up
    rm -rf "$DPDK_DIR" "$DPDK_FILE"
    # Want whitespace splitting here for multiple packages.
    # shellcheck disable=SC2086
    sudo yum remove -y $DPDK_BUILD_PACKAGES
    sudo yum groupremove -y "$DPDK_BUILD_GROUP"
    sudo yum autoremove -y
}

load_igb_uio() {
    # Need to load uio dependency first.
    sudo modprobe uio
    sudo modprobe igb_uio wc_activate=1
}

install_packages
install_ami_assets
build_igb_uio
load_igb_uio
