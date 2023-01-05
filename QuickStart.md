# Quick Start

This page details a quick start procedure for using the CloudFormation
templates in this repository to bring up XRd in EKS.

N.B. This is intended as an illustrative reference example and __should not__
be used in "real" deployments.

## Prerequisites

* `aws` cli installed with a profile with the required permissions
  * The account logged in must have administrator privileges (must be able
    to create IAM roles and create EKS clusters)
* An EC2 Key Pair
* An XRd image
* `helm`, `kubectl` and `skopeo` installed
* A clone of this repository.

## Bring up XRd topology

Clone this repository and execute the following commands from the
root of the repository:

```bash
./publish-ecr <path-to-xrd-image>
./publish-s3-bucket
./create-stack -u <XR-username> -p <XR-password> -k <key-pair-name>
```

* `create-stack` will take around one hour to complete.
* The topology includes two XRd instances providing a BGP L3VPN overlay over
  AWS, with an alpine containers attached to each of them to simulate a NF.
* `create-stack` sets the local `kubectl` context to point to the new cluster.

## Interact

* Inspect running pods

```console
-> kubectl get pods
NAME                                 READY   STATUS    RESTARTS   AGE
xrd-example-host1-78b766f567-jmczr   1/1     Running   0          15m
xrd-example-host2-6f948b8c5b-hd2dp   1/1     Running   0          15m
xrd-example-xrd1-0                   1/1     Running   0          15m
xrd-example-xrd2-0                   1/1     Running   0          15m
```

* Login to XRd

```console
-> kubectl exec -it xrd-example-xrd1-0 -- xr

User Access Verification

Username: user
Password:


RP/0/RP0/CPU0:xrd1#show interfaces brief
Wed Oct 19 10:56:08.533 UTC

               Intf       Intf        LineP              Encap  MTU        BW
               Name       State       State               Type (byte)    (Kbps)
--------------------------------------------------------------------------------
                Lo0          up          up           Loopback  1500          0
                Nu0          up          up               Null  1500          0
                ti1          up          up          TUNNEL_IP  1450        100
                ti2          up          up          TUNNEL_IP  1450        100
          Hu0/0/0/0          up          up               ARPA  1514  100000000
          Hu0/0/0/1          up          up               ARPA  1514  100000000
          Hu0/0/0/2          up          up               ARPA  1514  100000000

RP/0/RP0/CPU0:xrd1#exit
```

* Check ping from host1 to host2  across VPN
  * Note that `alpine` does not include `bash`, so to 'exec' to a shell use `sh`

```console
-> kubectl exec -it xrd-example-host1-78b766f567-jmczr -- ping -c 3 10.0.4.10
PING 10.0.4.10 (10.0.4.10): 56 data bytes
64 bytes from 10.0.4.10: seq=0 ttl=253 time=0.828 ms
64 bytes from 10.0.4.10: seq=1 ttl=253 time=0.786 ms
64 bytes from 10.0.4.10: seq=2 ttl=253 time=0.804 ms

--- 10.0.4.10 ping statistics ---
3 packets transmitted, 3 packets received, 0% packet loss
round-trip min/avg/max = 0.786/0.806/0.828 ms
```
