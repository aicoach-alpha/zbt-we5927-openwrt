# VeCI default GUI integration

This firmware uses **VeCI** as the default everyday router interface while retaining LuCI as an Expert fallback.

VeCI itself is maintained separately at:

- https://github.com/aicoach-alpha/veci
- interactive demo: https://aicoach-alpha.github.io/veci/

## Why it is separate

The generic VeCI project must remain reusable on other OpenWrt routers. Board-specific LTE/SIM behaviour stays in this firmware repository and is connected to VeCI through a small provider package.

The firmware therefore contains three pieces:

1. **veci** — pinned generic VeCI source from the standalone repository.
2. **veci-default-ui** — makes VeCI the uHTTPd default landing page without deleting LuCI.
3. **veci-cellular-we5927** — maps the existing WE5927 LTE manager onto the generic `veci.cellular` ubus API.

## Pinned source

The exact VeCI commit used for a firmware build is stored in:

```text
source/veci.commit
```

This prevents a firmware rebuild from silently picking up a newer GUI.

Prepare an OpenWrt tree with:

```sh
./scripts/prepare-veci.sh /path/to/openwrt
```

For an offline/local VeCI checkout:

```sh
VECI_SOURCE_DIR=/home/andre/veci ./scripts/prepare-veci.sh /path/to/openwrt
```

The script exports the pinned Git commit, not uncommitted working-tree files.

## Default UI behaviour

`veci-default-ui` changes the uHTTPd index-page order to:

```text
veci/index.html
<original index page(s)>
```

It does **not** overwrite LuCI and does not remove `/cgi-bin/luci/`.

Runtime controls:

```sh
veci-default-ui status
veci-default-ui disable
veci-default-ui enable
```

If VeCI is disabled, the original uHTTPd index-page list captured on first activation is restored.

## Hardware identity

VeCI continues to obtain the router manufacturer/model from OpenWrt's live `system.board` data. The generic GUI does not hardcode WE5927.

The WE5927-specific package only provides cellular capability data.

## Cellular contract

The provider registers:

```text
ubus object: veci.cellular
methods:
  status          # periodic lightweight status; NO IMEI/ICCID
  identity        # explicit read of cached IMEI (authenticated)
  identityLive    # explicit read-only AT+CGSN query (authenticated)
  reconnect       # user-confirmed data operation
  switchSim       # user-confirmed SIM operation
```

`status` is sourced from `we5927-lte status-fast` and returns only the normal cellular monitoring fields. **IMEI and ICCID are not present in periodic status payloads.** IMEI is available only after the authenticated user requests it through `identity` or `identityLive`; ICCID is not forwarded at all. The generic VeCI UI has no modem-specific AT parsing.

`identity` reads the cached result previously obtained by the WE5927 LTE manager and includes cache age and stale metadata. `identityLive` requests **read-only** `AT+CGSN` through the manager's serialized, bounded AT transport. If the modem is disconnected, unresponsive, or the AT port is busy, the read fails closed; it must never restart the modem or fall back to a guessed identifier. Both paths validate the 15-digit response. IMEI is revealed temporarily on the Cellular page and automatically hidden after 60 seconds; VeCI must not persist it in browser storage, telemetry, or logs.

A modem's vendor web management UI can report a different identity from the modem's AT command interface, including when a stored/vendor value is outdated. **Matching cached and live AT values only establishes agreement between those two interfaces; it does not prove what the operator sees, whether an identifier is registered, or the legality of its use.** Do not overwrite, synchronize, or program any identifier to make two displays match. Verify discrepancies with the device supplier and official registration channels.

`reconnect` and `switchSim` are explicit write operations and run through the existing tested LTE manager rather than duplicating modem logic.

### Read-only identity diagnostics (WE5927 shell)

Use these only on a device you administer. **Do not paste full IMEI/ICCID or authentication credentials into issues or chat transcripts.**

```sh
for mode in status-fast status-full; do
  printf '%s: ' "$mode"
  /usr/sbin/we5927-lte "$mode" 2>/dev/null |
    jsonfilter -e '@.imei' 2>/dev/null |
    awk 'length($0)==15 && $0 ~ /^[0-9]+$/ {print "****" substr($0,12,4); next} {print "not available"}'
done
```

`status-full` uses `ATI` first and falls back to `AT+CGSN` when needed. The optional `imei-read` command (included only in the new firmware source) uses `AT+CGSN` directly and returns structured JSON. Do not assume the command exists in older installed images.

UAT acceptance requires an authenticated session, explicit reveal, masked screenshots, cache-age handling, busy/offline error handling, no modem writes, and a 60-second automatic hide. Live-device UAT is separate from non-live CI.

## Build order

For a one-command build from a clean pinned OpenWrt tree:

```sh
JOBS=4 ./scripts/build-veci-firmware.sh /path/to/openwrt
```

The script verifies the exact OpenWrt commit, requires a clean source tree, applies the firmware overlay, resolves the pinned VeCI source, installs feeds, builds the image, and rejects an image larger than the 7808 KiB device budget.

For a reproducible firmware build:

1. checkout the OpenWrt source commit recorded in `source/openwrt-source-commit.txt`;
2. apply the board/target patch;
3. install `source/we5927-lte`;
4. run `scripts/prepare-veci.sh <openwrt-root>`;
5. copy `source/openwrt-we5927.config` to `.config`;
6. run `make defconfig`;
7. build normally.

## Release gates

VeCI must not become the public stable default until all of these pass:

- generic VeCI CI;
- pinned-source preparation test;
- OpenWrt package build;
- image-size / overlay-budget check;
- live login and navigation;
- LuCI Expert fallback;
- native Wi-Fi editing;
- cellular status/reconnect/SIM switch;
- root landing page -> VeCI;
- `veci-default-ui disable` -> original landing page;
- router reboot;
- LTE recovery regression;
- Router Apps end-to-end: Guest portal, Smart Queue, Dynamic DNS, WireGuard and Voucher install/configure/remove tests;
- exact-ABI VeCI app feed validation with no blind package upgrade;
- native VeCI firmware updater: manual image validation plus GitHub release-channel discovery;
- firmware board/target/checksum validation before any install action;
- `sysupgrade -T` on the exact release image.

No official/final router flash is performed while any Router App or firmware-update gate above remains incomplete. The existing RC1 remains the recovery baseline until a VeCI-enabled image passes every gate and the operator explicitly approves the final flash.


## Firmware updater

VeCI contains a native firmware updater; the WE5927 release source is supplied by `veci-update-we5927` so the generic core does not hardcode a router model or project repository.

The native flow is deliberately two-phase:

1. stage a firmware image, either by chunked browser upload or the configured GitHub release channel;
2. verify size and SHA256, then require `sysupgrade -T` to pass;
3. create a short-lived validation token bound to the exact file hash and running board;
4. enable the destructive Install & reboot action only for that validated file.

The WE5927 profile points to:

`https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/app-feed/channel-stable.json`

Automatic checking is enabled by default. Automatic download is opt-in. A downloaded image is staged and validated but is not flashed automatically while signed firmware release metadata is not yet provisioned.

The release publisher creates the GitHub firmware release and exact matching Router Apps feed from the same build run, then updates the stable channel metadata. No final release workflow should be dispatched until all Router Apps and live regression gates have passed.
