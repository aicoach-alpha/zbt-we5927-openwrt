# J9 — VeCI WE5927 UAT readiness

**Status: OFFLINE PASS / LIVE UAT NOT TESTED / FLASH NO_GO.** This document is a release gate, not permission to flash or install anything.

## Paired J8c evidence

- Run [37913407078](https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/37913407078), SUCCESS on Oct 9, 2026. Firmware source commit: `a919b15bc43f91071c9c655e1a557d8a0e4d5962`.
- Firmware artifact: `veci-j8c-maintenance-candidate` ID `11612776687`.
- Exact-ABI feed artifact: `veci-j8c-matched-app-feed` ID `11612632081`.
- These artifacts expire October 23, 2026. If expired, build *both* artifacts in a new single run.
- J8c candidate kernel: `6.12.112`; old live WE5927 kernel observed earlier: `6.12.94`. Never use the J8c feed on the old firmware.

## Automated J9 offline gate

Workflow: `.github/workflows/j9-readiness.yml`. Download the firmware and app feed **from the same run ID**, then run the unit tests and `scripts/j9_offline_audit.py`. The workflow has only read permission and cannot flash the router. Run by push or manually with an explicit successful J8c run ID.

Manual audit (directories extracted by GitHub Actions, or ZIPs):

```sh
python3 -m unittest discover -s tests -p 'test_j9_offline_audit.py' -v
python3 scripts/j9_offline_audit.py \
  --firmware firmware-artifact.zip --feed matched-feed-artifact.zip \
  --run-id 37913407078 --report j9-readiness.json
```

Checks: SHA256 of firmware, manifest and inventory; OpenWrt target checksum cross-check; image <= 7808 KiB; required base firmware packages; optional apps excluded from base; immutable source pins; required APK files and four indexes; selected APK inventory sizes; kernel version match for the relevant kmods; reject corrupt/unsafe/duplicate archive paths.

**Not checked:** APK signature authenticity, full APK dependency solving, installation on a router, access controls, guest/voucher credentials, firewall correctness, sysupgrade device compatibility, OTA signing flow. A matching image and feed by run ID is process assurance, not cryptographic proof of shared provenance. J9 always emits `release_decision: NO_GO`.

## Physical-UAT prerequisites — mandatory, blocked now

Before any destructive test: verify exact board/flash layout, assess free RAM and overlay, securely back up settings, document and confirm actual recovery route, verify image/manifest identity and signed package indexes, identify a recoverable test router, and obtain **explicit operator approval for that exact image + device + maintenance window**. No flash is authorized just by passing offline CI.

## Hardware UAT matrix (do not run on production/live router yet)

| Component | Acceptance criteria | Status |
|---|---|---|
| VeCI auth | Login, logout, expiry, ACL checks, unauthenticated access rejected | NOT TESTED |
| LuCI | Expert fallback and reversible default landing page | NOT TESTED |
| LAN/Wi-Fi | LAN remains accessible, Wi-Fi edit, reboot persistence | NOT TESTED |
| LTE/RNDIS | WAN and Internet health distinct, AT port busy fails safely, SIM operations recover | NOT TESTED |
| IMEI | Cached vs live AT+CGSN source labeled, no IMEI write, no identifying logs, hide after 60 seconds | NOT TESTED |
| Guest Portal | Portal interception, unauthenticated isolation, DNS/DHCP, trusted LAN inaccessible, rollback | NOT TESTED |
| SQM | Correct ABI modules, CAKE/IFB functionality under load, acceptable CPU/RAM, disable restore | NOT TESTED |
| DDNS | Controlled update, token privacy, retries, uninstall/rollback | NOT TESTED |
| WireGuard | Handshake, firewall/routing, no unintended LAN exposure, uninstall and recovery | NOT TESTED |
| Voucher | Valid credentials, expiry, revoke disconnect, cleanup, guest integration — APK build alone insufficient | NOT TESTED |
| App catalog | Verify signed index, all five app install/config/remove, never blind apk upgrade | NOT TESTED |
| Firmware updater | Manual upload, checksum and board check, signed channel, sysupgrade -T, token expiry, rollback | NOT TESTED |
| Recovery | Reboot, persistence, fallback, storage and LTE recovery | NOT TESTED |

Read-only inventory is permitted if requested by the operator; do not change WAN, modem, IMEI, persistent config, reboot, flash or install any app without a test plan and consent. The MiFi vendor page can show an IMEI different from the modem AT response; neither display proves operator registration status.

## GO decision

Release remains **NO_GO** until every Router App, native updater, firmware compatibility, recovery, and live UAT gate passes, and the owner explicitly authorizes the final device flash. J8c artifact passing means a reproducible build candidate, not a production release.
