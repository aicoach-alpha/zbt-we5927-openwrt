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

## Prevent VeCI SPA rollback / provenance drift

A second read-only tool computes public static-asset SHA-256 entries under
`/www/veci` and can compare the candidate image to a **fresh, operator-verified
production** UI manifest. It does not read `/etc/config`, keys or session data.

Capture an inventory from an approved source (not the outdated 2026-10-28 UI
archive), then compare a candidate extracted rootfs:

```sh
python3 scripts/veci-rc-ui-provenance.py --ui-root /trusted/current/www/veci > current-veci-manifest.json
python3 scripts/veci-rc-ui-provenance.py --ui-root /staged/root-ramips/www/veci \
  --approved-manifest current-veci-manifest.json
```

An unchanged UI passes. Any missing/extra/modified assets fail closed to avoid
accidental replacement of a stable production UI while only LTE/Wi-Fi drivers
are being updated. If a **planned VeCI upgrade** changes UI assets, first
qualify that change independently and approve its new manifest. A hash match
alone never proves that UI login, full LuCI parity, or OTA flows work.

The public `aicoach-alpha/veci` source currently has its own OpenWrt package,
but native-feature documentation still lists advanced network, backup, OTA
and other functionality as LuCI Expert. Its checked-in main commit dates back
to 2026-10-15; therefore copying it into a 2026-11-12 RC without current live
source comparison could downgrade the router UI. The reliability RC must not
auto-install that generic package in place of an unknown newer live SPA.
