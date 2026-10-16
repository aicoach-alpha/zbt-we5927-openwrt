# WE5927 SMS Inbox v1.3 rollback PASS — rpcd plugin registration diagnosis

Date: 2026-10-13 Asia/Jakarta. Official status: physical v1.2 SMS storage UI is LIVE/PASS, v1.3 Inbox is NOT LIVE.

## Physical operator evidence

After an attempted v1.3 install returned `INBOX_V13_ERROR: rpc_registration_not_visible` and `INBOX_V13_AUTOMATIC_ROLLBACK_STARTED`, owner performed entirely read-only checks:

- `/www/veci/js/pages/cellular.js` SHA256 `2deb013e6ccf433b9c3abc3d7f02aafb33739dd1b5b5f222d4de501865314d40`: exact restored v1.2.
- `INBOX_RPC=absent`, `INBOX_WORKER=absent`, `INBOX_ACL=absent`.
- Old failed-install recovery directory exists at `/root/veci-sms-inbox-v13-rollback` (do not overwrite/delete).
- `ubus list 'veci.*'` returns only `veci.cellular`.
- `ps` confirms rpcd running under root PID 7054.
- `logread -e rpcd` showed procd killed old rpcd PID 6953 after no stop response to SIGTERM. This alone does not explain absent registration. The original installer checked registration immediately after restart; a restart race remains plausible, **not confirmed**.
- Overlay approx 1.7 MiB free; no LTE degradation or modem query was reported.

## Upstream mechanism

OpenWrt rpcd scans executable plugins in `/usr/libexec/rpcd` on startup. Each is executed with `list` and must return a valid JSON signature to register a ubus object. The basename provides the object name. See:

- https://openwrt.org/docs/techref/rpcd
- https://lxr.openwrt.org/source/rpcd/plugin.c (rpc_plugin_register_exec, rpc_plugin_api_init)

## Safe read-only hardware preflight, run FIRST

The new immutable script `scripts/veci-sms-rpcd-readonly-preflight-20261013.sh` fetches *only* the originally pinned v1.3 RPC shell file into `/tmp`, verifies exact SHA256, checks `sh -n`, executes **`sh <file> list` ONLY** (never `call`), validates two JSON signature fields, queries only ubus presence and existing backup hash, and removes the temporary file. It neither writes system directories nor sends modem AT, reads SMS, reloads rpcd or restarts services.

```sh
cd /tmp
wget -O veci-rpcd-readonly-preflight.sh \
  https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/cfc8007963060d8392387b3952463bf6e5f345aa/scripts/veci-sms-rpcd-readonly-preflight-20261013.sh
sh -n veci-rpcd-readonly-preflight.sh && sh veci-rpcd-readonly-preflight.sh
```

Expected success marker: `RPCD_PLUGIN_LIST_CONTRACT_PASS`; expected `LIVE_V12_SHA=2deb...`, `EXISTING_CELLULAR_RPC=registered`, `SMS_INBOX_RPC=absent`, `V13_FAILED_INSTALL_BACKUP=valid_v12`. If any value differs, STOP; do not retry v1.3 or v1.3.1.

## Fixed v1.3.1 candidate (not yet applied)

`scripts/veci-sms-inbox-admin-ui-v131-install.sh` uses a *different*, private rollback path `/root/veci-sms-inbox-v131-rollback`, leaving failed v1.3's backup untouched. It checks the old `veci.cellular` object before any modification, checks the plugin `list` signature using on-device `jsonfilter` before install, checks all pinned payload hashes, restarts rpcd once, and waits up to 12 seconds for `veci.sms` **and** `veci.cellular` registration. A failure triggers automatic rollback; it must not report success prematurely. Installation itself never reads SMS or sends AT commands. On success, explicit user click and consent are still needed for any actual inbox listing (which can mark unread messages read).

**388/388 offline host tests PASS** including bounded delayed-registration success and failure-with-rollback; https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38336460060. Physical v1.3.1 untested. Do not claim v1.3.1 LIVE.

## Physical safety

- Never SSH from NAS to its unrelated 192.168.1.1 ZTE device. Only from office laptop to real WE5927.
- No need to repeat prior `AT+CMGL=4` reading to check registration.
- Existing live v1/v2/v1.2 backups remain intact; UI stored SMS count is already operational.
