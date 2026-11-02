# Pinned OpenWrt snapshot identity for General-Cafe release validation

The built WE5927 image from 2026-10-31 carries release metadata:
- dist: OpenWrt
- version: 25.12-SNAPSHOT
- revision: r0+1-c74057035
- board: zbtlink_zbt-we5927
- target: ramips/mt76x8

This is the build's actual version string from the pinned OpenWrt source
commit c740570351512e4400369b3c2aff49741f65580e. The source
Makefile defaults to 25.12-SNAPSHOT, despite the product being based on
the OpenWrt 25.12 release series. It is not evidence of the official
25.12.5 release label.

The standalone image verifier accepts either 25.12.5 or the exact pinned
snapshot version AND revision together. It refuses arbitrary snapshot
versions/revisions. The finalizer additionally validates the exact OpenWrt
git commit and the embedded VeCI source build id, firmware partition
size and SquashFS rootfs. This fix changes only the release verification
logic: no router firmware or deployed configuration is modified.

Successful source and image checks NEVER approve physical flashing.
An image lacking the device-approved firmware signature remains
blocked for the automated update path; signed APK index verification is
a different check. Physical recovery and router UAT remain mandatory.
