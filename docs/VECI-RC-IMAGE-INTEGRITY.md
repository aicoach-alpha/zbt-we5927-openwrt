# VeCI RC1 offline image integrity and no-flash attestation

Status: **build artifact QA only**, not signing, physical UAT, or deployment.
This gate has no network requests and no router access.

Once GitHub's WE5927 full-image workflow has a finished image, extract its
metadata with the build-tree **host** `fwtool -i` and identify the exact staged
`root-ramips` directory. Run:

```sh
python3 scripts/veci-rc-image-integrity.py \
  --image /build/bin/targets/ramips/mt76x8/openwrt-*-zbtlink_zbt-we5927-squashfs-sysupgrade.bin \
  --metadata /build/sysupgrade-metadata.json \
  --rootfs /build/build_dir/target-*/root-ramips \
  --source-lte source/we5927-lte/files/usr/sbin/we5927-lte
```

Replace globs with a single exact path; the script intentionally receives
explicit arguments rather than guessing from possibly multiple artifacts.
The tool does **not** run `sysupgrade`, `mtd`, `wifi`, UCI, or USB commands.

Hard gates: exact tested hardware's 0x7a0000-byte firmware partition, board
`zbtlink,zbt-we5927`, target `ramips/mt76x8`, OpenWrt 25.12.5 metadata,
the staged LTE shell script byte-for-byte matching vetted build source, and a
Guardian script explicitly indicating no radio auto-recovery. Evidence
includes SHA-256, image size and any blockers, without printing sensitive
network or modem details.

An installed `/www/veci/index.html` is reported only as one indicator of UI
packaging, **not proof** that authentication/features work. A missing native
VeCI SPA still blocks production release under PR #16; a successful integrity
result is not production approval.

The JSON output has `production_flash_authorized:false` regardless of outcome.
Image signing, backup, ART/calibration and U-Boot protection, wired `sysupgrade -T`,
two-phone SSID visibility, LTE across repeated ~122-minute windows, 72-hour
stability, SMS and safe OTA rollback are separate gates.
