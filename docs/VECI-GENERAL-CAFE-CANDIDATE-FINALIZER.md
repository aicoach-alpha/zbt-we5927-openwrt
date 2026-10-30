# VeCI General-Café offline candidate release gate

After a complete OpenWrt build and no concurrent make process, execute the finalizer on NAS using the pinned source and original build tree:

    python3 /home/andre/projects/veci/worktrees/candidate-finalizer/scripts/finalize-veci-cafe-candidate.py --firmware /home/andre/projects/veci/worktrees/candidate-finalizer --build-tree /mnt/data/andre-maintenance-archives/veci-cafe-build-20261029/openwrt --output /mnt/data/andre-maintenance-archives/veci-cafe-build-20261029/candidate-verified

The output must not already exist. The original OpenWrt SHA must be c740570351512e4400369b3c2aff49741f65580e. The staged firmware build_id must point to a real ancestor Git object, whose source/veci.commit matches the staged Core pin. A matching host fwtool, exact image/manifest count, board/version/size, required LTE + Guest/Voucher package inventory and SHA256 are mandatory.

Output is private: RELEASE-CANDIDATE.json, SHA256SUMS, image and manifest. It does not publish, install apps, access the router, or flash firmware. Success retains FLASH_DECISION=NO_GO_UNTIL_HARDWARE_RECOVERY_AND_UAT. Firmware source testing is not evidence of bootability or recovery. Verify actual flash partition size and physical rescue before manual upgrade.


## Actual embedded root filesystem attestation

The gate also requires the host unsquashfs utility and exactly one SquashFS
header inside the sysupgrade image. It extracts, into an ephemeral local
directory, the actual firmware release JSON, Core RPC, signed-feed RPC,
Guest/Voucher RPC scripts, VeCI HTML and bundled APK public trust keys.
All release pin fields must match source metadata. Missing files, empty
trust keys, symlinks, image extraction errors, or a mismatch are a hard
NO-GO, even if the manifest lists all packages.

The generated candidate is still not a deployable production release.
The tester must separately verify signatures, hardware boot, LTE,
guest isolation, captive portal login, voucher expiration and rollback.

## Actual device flash capacity evidence (operator attested)

On 30 October 2026 at 12:01 WIB the operator ran a read-only,
SHA256-pinned flash capacity audit against the physical ZBT WE5927.
Board: zbtlink,zbt-we5927; target: ramips/mt76x8; kernel: 6.12.94.
The firmware MTD size was 0x007a0000 = 7,995,392 bytes (7,808 KiB).
The audit retained FLASH_DECISION=NO_GO.

The operator-reported evidence is in docs/WE5927-OPERATOR-MTD-EVIDENCE-20261030.json.
The finalizer requires this evidence and independently verifies exact board,
size, release-gate fields, and actual image byte size. It reports remaining
partition bytes but this equality check cannot prove hardware bootability.

This is operator-provided data, NOT a cryptographic router attestation.
Do not flash automatically. After offline candidate verification, physical
boot, rescue procedure, LTE, captive portal, voucher authentication and
restored settings still require manual UAT and explicit approval.

## Stale build guard

Default release validation requires staged build_id equal to current tested HEAD. Historical ancestor builds are rejected with STALE_BUILD_REQUIRES_REBUILD. For offline inspection use --audit-stale, which marks output HISTORICAL_AUDIT and NO_GO_STALE_BUILD_REQUIRES_REBUILD. This is never permission for flashing. Current-source builds must still pass recovery and hardware UAT.
