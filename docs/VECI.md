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
  status
  reconnect
  switchSim
```

`status` is sourced from `we5927-lte status-fast` and returns only the fields the VeCI cellular page needs. Device identifiers such as IMEI and ICCID are deliberately not forwarded into the generic GUI API.

`reconnect` and `switchSim` are explicit write operations and run through the existing tested LTE manager rather than duplicating modem logic.

## Build order

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
- `sysupgrade -T` on the exact release image.

The existing RC1 remains the recovery baseline until a VeCI-enabled image passes those gates.
