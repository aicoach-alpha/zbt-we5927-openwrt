# MT7603/WE5927 — build, safety gates, and hardware UAT

**Status:** source fixes only until a complete exact-board signed image is available. A passing GitHub build is **not** permission to flash.

## Build — automated in GitHub Actions

Workflow: `.github/workflows/veci-mt7603-crossbuild.yml`

1. Check out the exact pinned OpenWrt source commit in `source/openwrt-source-commit.txt` (25.12.5, Linux 6.12.94).
2. Apply `source/openwrt-zbt-we5927-current.patch`, then stage both pinned `mt7603` patches using `scripts/stage-mt7603-deadlock-fix.sh`.
3. Apply the WE5927 `.config` and run `make defconfig`; install host tools and cross-toolchain.
4. **Compile the kernel target, not only `target/linux/prepare`.** The latter previously left Linux `.config` missing, which failed the `gpio-button-hotplug` prerequisite.
5. Compile `package/kernel/mt76/compile`; prove a **non-empty** `mt7603e.ko` exists; collect SHA-256. Keep build logs; no module from a different ABI should ever be copied into the running system.
6. The existing patch-gate CI validates patch applicability and rejection of mismatched pinned revisions separately.

The build workflow intentionally does not upload a flashable image. It demonstrates compilation only, not complete firmware integration, signing, boot, beacon correctness or uptime.

## Full-image release gate (must all PASS before flashing)

- Exact target `ramips/mt76x8`, device `zbtlink,zbt-we5927`, OpenWrt 25.12.5 and kernel ABI verified.
- Board variant, NOR flash partition layout and current installed image metadata match the actual router.
- Both `mt7603` patches are present in the compiled source, the **new** 1,032-line-plus LTE watchdog is staged with `scripts/reconcile-we5927-lte-build-tree.sh` **after** the historical board patch, and the safe Wi-Fi Guardian is staged with `scripts/stage-veci-wifi-guardian.sh` and selected in the image config.
- Preserve existing VeCI guest script and `uhttpd.veci_guest.enabled=0` while guest is disabled; verify live version is not overwritten by the historical board patch.
- Build full system image; inspect image size, supported devices metadata, signing/trust anchor and installed package manifests. `sysupgrade -T` on the physical router **only after** confirming exact image format and metadata; no forced upgrade.
- Back up config and independently validate firmware/recovery path. Never touch ART/calibration partitions. Require wired Ethernet administration, steady power/UPS, and a known-good signed rollback image.
- The image must be tested as one unit. Do not `opkg upgrade` the radio driver or load mismatched `.ko` while the device is live.

## Hardware UAT matrix

| Test | Required observation | Pass threshold |
|---|---|---|
| Boot/login | VeCI HTTPS and SSH reachable; `rpcd` and `hostapd` running normally | No blocked D-state process; login works |
| External SSID visibility | Independent Windows Wi-Fi scan and two phones detect the primary SSID | No unexplained SSID disappearance during acceptance window |
| Clients/security | Associate WPA2 and WPA3 clients; measure DHCP, DNS, LAN and internet | 2 phones plus independent scan; successful reassociation |
| MT7603 kernel | Read-only `mt76/reset` counters and `dmesg` | No unhandled MCU timeout / reset failure / driver deadlock |
| Real traffic | Wi-Fi local LAN traffic and Internet across continuous use | No unexplained beacon disappearance or connection drop |
| LTE independence | Monitor local modem gateway, two public IPs, HTTPS and PDP state | No automatic DHCP release/interface flap on public-only failures |
| Long-window reliability | Observe from preflight, boot, +10min, +1h, +6h, +24h, +72h | Must cover the prior 121–122-minute recurrence multiple times |
| Guest off | Guest SSID disabled, no premature `uhttpd` bind | Main SSID stays available; no guest startup loop |
| Guest on (later) | Captive redirect, guest DHCP/DNS, client isolation, correct firewall | Explicitly enabled only after primary radio UAT passes |
| Rollback | Restore known-good signed firmware and saved settings if health gates fail | Verified rollback path; do not deliberately brick for a test |

**Not acceptable as UAT evidence:** `radio0.up=true` or `hostapd.status=ENABLED` alone. Both were true while an independent laptop could not detect the SSID on multiple occasions.

## Responsibilities

GitHub Actions handles compilation and source checks automatically. A Windows laptop on **wired Ethernet** can run read-only telemetry and SSID scanning. A person only needs to check the two real phones and confirm service after an approved image installation. No manual SSH build commands are required.

**Go/no-go:** do not deploy if kernel cross-build is red, if an image is unsigned/mismatched, if the old LTE or Guardian code would be restored, or if a tested recovery path is absent. Never automatically flash a production router as part of CI.
