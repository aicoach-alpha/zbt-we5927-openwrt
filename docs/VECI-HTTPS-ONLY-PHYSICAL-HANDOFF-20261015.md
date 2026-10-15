# VeCI HTTPS-only — approved guarded migration (2026-10-15)

**User approval:** HTTPS-only administration approved. Do not interpret this approval as evidence HTTPS connectivity already works. Keep HTTP enabled until the owner confirms real HTTPS access from the authorized office laptop.

## Exact staged controller

`scripts/veci-https-only-guarded-migration-20261015.sh`

Target: **physical ZBT-WE5927 OpenWrt 25.12.5**, `root@192.168.1.1`, invoked **only from Windows office laptop `25NBCABA13CF`**. Do not execute on `andre-nas`.

Focused mocked uhttpd CI: https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38715986005 — **PASS**.
The scope is only /etc/config/uhttpd and /etc/init.d/uhttpd; no changes to VeCI Core 0.2.2, LuCI, SIM, SMS, LTE, network or packages.

## Steps and guardrails

1. `--status` — read-only uhttpd listener/TLS-file status.
2. `--prepare` — validate board, firmware, root, TLS cert/key files and nohup; save a root-owned 0700 **persistent copy of original uhttpd config** with SHA256; enable HTTPS listener if missing; **retain HTTP**; restart uhttpd only if the listener was added. A failed early preflight makes no configuration changes.
3. Open `https://192.168.1.1/veci/` in a normal browser from the office laptop and **complete actual administrator sign-in**. Verify that VeCI pages load over HTTPS. Do not enter XL number or OTP until this works.
4. **Only after browser HTTPS login is confirmed**, invoke `--switch`: verifies staged config hash, starts detached rollback watchdog, deletes only `uhttpd.main.listen_http`, commits uhttpd, restarts uhttpd, checks HTTPS listener/config still present.
5. Within **180 seconds**, verify VeCI still loads and authenticates over HTTPS and invoke `--confirm`, or let watchdog restore the exact original uhttpd. `--rollback` remains available from root SSH even after `--confirm`.
6. The account owner can then use separate *signed* XL Native 0.3.7 installer `--status` and `--verify`. Its `--install` also requires **locally authorized operator configuration**, which is not yet proven present. Do not claim authenticated quota based on APK signing or UI tests.

## Access limitation

Desktop Commander returned a **monthly usage quota** block for the office laptop connection; SentinelX has an agent on `andre-nas` only and must not be used as a substitute. No physical router command was executed in this migration work. If the owner is to run a physical step, it must be the shortest PowerShell SSH command from their office laptop.

## Production recovery

`/root/veci-https-recovery-20261015/original-uhttpd` and `original-uhttpd.sha256` hold the original config on persistent overlay. The watchdog auto-restore runs at 180 seconds if `--confirm` is absent. SSH access remains the fallback for `--rollback`. A reboot during the watchdog period may stop the watchdog: maintain SSH access and the persistent backup throughout the transition. Do not switch without browser-side HTTPS verification.

**Not done:** physical HTTPS-only switch, verification of valid TLS chain, XL operator credential provisioning, OTP delivery, real quota. Do not report these as PASS.
