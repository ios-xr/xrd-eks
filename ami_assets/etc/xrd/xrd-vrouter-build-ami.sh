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

# Additional packages required to build igb_uio
DPDK_BUILD_PACKAGES="""
kernel-devel-$(uname -r)
"""

# The ami_assets to retrieve from the S3 bucket
AMI_ASSETS="""
/etc/xrd/bootstrap.sh
/etc/xrd/hugetlb-reserve-pages.sh
/etc/modprobe.d/vfio.conf
/etc/modprobe.d/igb_uio.conf
/etc/modules-load.d/vfio-pci.conf
/etc/modules-load.d/uio.conf
/etc/modules-load.d/igb_uio.conf
/etc/systemd/coredump.conf
/etc/tuned/xrd-eks-node-variables.conf
/etc/tuned/xrd-eks-node/defirqaffinity.py
/etc/tuned/xrd-eks-node/tuned.conf
/usr/lib/systemd/system/hugetlb-gigantic-pages.service
"""

DPDK_KMODS_VER=${DPDK_KMODS_VER:-"e721c733cd24206399bebb8f0751b0387c4c1595"}
DPDK_KMODS_DIR=${DPDK_KMODS_DIR:-"dpdk-kmods-${DPDK_KMODS_VER}"}
DPDK_KMODS_ARCHIVE=${DPDK_KMODS_ARCHIVE:-"${DPDK_KMODS_DIR}.tar.gz"}
DPDK_KMODS_URL=${DPDK_KMODS_URL:-"https://git.dpdk.org/dpdk-kmods/snapshot/${DPDK_KMODS_ARCHIVE}"}


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
    # Want whitespace splitting here for multiple packages.
    # shellcheck disable=SC2086
    sudo yum install -y $DPDK_BUILD_PACKAGES

    curl -O "$DPDK_KMODS_URL"
    tar zxvf "$DPDK_KMODS_ARCHIVE"

    cd "$DPDK_KMODS_DIR"
    make -C linux/igb_uio

    sudo cp linux/igb_uio/igb_uio.ko /lib/modules/"$(uname -r)"/kernel/drivers/uio
    sudo depmod -a

    cd ..

    # Clean up
    rm -f "$DPDK_KMODS_ARCHIVE"
    rm -rf "$DPDK_KMODS_DIR"
    # Want whitespace splitting here for multiple packages.
    # shellcheck disable=SC2086
    sudo yum remove -y $DPDK_BUILD_PACKAGES
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
