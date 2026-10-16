# Corrected WE5927 VeCI SMS storage-count UI hotfix (v1.1)

Date: 2026-10-12. Status: CI PASS, physical deployment NOT YET performed.

## Root cause of v1 safe refusal

User downloaded and ran the v1 installer from immutable firmware commit
`1d9100012d271b421ddcdc732760ae316e02d834`. It stopped before any
file changes with:

```
UI_ERROR: Installed Cellular differs from pinned base: untouched
```

This is expected if the router carries compiled/minified VeCI assets.
`veci/scripts/build.js` uses Terser minify with module=true and
compress passes=2; OpenWrt Makefile copies `dist/veci` when built.
The initial v1 hotfix compared installed `/www/veci/js/pages/cellular.js`
with the 12.8 kB UNMINIFIED upstream source. An intentional local
modification or another firmware asset version can also cause mismatch.
The observed refusal alone does NOT establish which cause applies to this
physical router until its on-device SHA256/byte count is examined.
No UI write or v1 UI rollback backup occurred from this refusal.
Existing messagingStorage, messagingCapabilities and LTE services are unaffected.

## Corrected build artifacts

Compiled via the actual VeCI build Terser configuration, produced in a
GitHub CI job using immutable source refs. The three exact assets were
committed as raw minified JavaScript to:
`scripts/veci-sms-storage-ui-built-v1/` at immutable SHA
`15f8a6afd4e16ff8f58bcfe5545f045fc3f943cf`.

| Payload | Bytes | SHA256 |
|---|---:|---|
| expected-cellular.js | 9829 | a2c62cbf42909951b73127a4ee1bfef60cf7d8654ee274f41e997001444a7aa4 |
| new-cellular.js | 10769 | ec74f3f575d35df073c7b839ab687103fba6557f2cf7e7136b7922a0150e7d65 |
| new-messaging.js | 642 | 50d5aba460b8b5b20c256cdf72bd41e660444ab59e2c1f4e5094edd9bb5277ac |

These payload byte hashes are verified by CI directly from repository
files, not just by naming conventions.

## Reversible one-time overlay

Script: `scripts/veci-sms-storage-ui-built-hotfix-v11.sh`.
It verifies the router board and installed Cellular file SHA-256
**before** making any changes. If actual installed minified hash is not
the expected `a2c62...`, it prints actual SHA and byte count and exits
without modifying the UI. Do not weaken this check; resolve the
exact local firmware asset provenance first.

When compatible, it downloads all three immutable files, validates all
byte hashes, backs up existing Cellular to the separate persistent
`/root/veci-sms-storage-ui-v11-rollback`, installs the formatter and
Cellular page atomically and verifies both installed hashes. Automatic
rollback is attempted after failed installation. Manual `rollback`
restores prior UI after verifying prior content, without touching LTE.

Source of the updated UI: aicoach-alpha/veci development PR #7
https://github.com/aicoach-alpha/veci/pull/7

Only new behavior: a human-clicked SMS storage counter based on the
already proven `veci.cellular.messagingStorage` RPC; no SMS inbox
listing, raw PDU output, OTP, messaging loop or USSD transaction.

CI: 339/339 host regressions PASS
https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38232731740
including six new byte-level minified payload and UI rollback guards.

## Operator-only verification

Use authorized office Windows -> physical WE5927 SSH session. The
router is NOT reachable through the NAS path assumed in older chats.

First download the pinned revised installer into `/tmp` and run
`sh -n` followed by the `status` operation. Compare actual sha.
If it matches, use `apply`; if it differs, stop and preserve the actual
SHA and byte count for provenance investigation. No forced overwrites.

After successful apply, browser hard refresh Cellular and click
`Check stored SMS count` once. UI rendering itself has NOT been
physically observed, so installer PASS is not end-to-end dashboard PASS.

Rollback only this UI hotfix with its `rollback` operation. Do NOT touch
`/root/veci-capability-hotfix-rollback` or
`/root/veci-storage-hotfix-rollback`.


## Owner-observed v1.1 refusal — unrecognized installed asset

On 12 October 2026, the owner ran the pinned 5,246-byte v1.1 script
from firmware SHA `61130c9f033f32aaa706331c285dd0ed1920fc96` on the real
WE5927 via office-laptop SSH. The read-only `status` call and protected
`apply` confirmed:

```text
CURRENT_CELLULAR_SHA=0a4e78d5368806b31441612b8979ab7b2ac8f425890cfd89104f969accd8ee18
EXPECTED_MINIFIED_SHA=a2c62cbf42909951b73127a4ee1bfef60cf7d8654ee274f41e997001444a7aa4
CURRENT_CELLULAR_BYTES=6357
HELPER_SHA=absent
V11_BACKUP=none
UI_V11_ERROR: installed_asset_not_verified_untouched
```

Overlay remains approx. 1.7 MiB available (364 KiB used of 2.1 MiB).
No installation was performed. The v1.1 script correctly protected the
unknown local Cellular asset and retained v1/v2 LIVE modem RPCs.

### Independent historical asset investigation

Compiled each historical `veci/js/pages/cellular.js` commit on all known
VeCI branches with the exact official Terser build options and compared
its SHA256 with the actual installed hash. **None of 12 compiled historical
variants matches** `0a4e78d5...d8ee18`. Source: VeCI quality run
https://github.com/aicoach-alpha/veci/actions/runs/38236031989.
This may be a custom locally patched asset or another build/version; do NOT
infer provenance without inspecting the installed file.

**NO-GO** for any full-file Cellular replacement at this point.
The next safe path is to acquire a read-only copy of the live
`/www/veci/js/pages/cellular.js` from the *office Windows laptop* and
analyze its anchors/functionality, then build a minimal, content-addressed
patch or an isolated add-on with its own rollback. Do not SSH to
192.168.1.1 from andre-nas (that is a different ZTE device).

Read-only Windows PowerShell command from the office laptop:

```powershell
scp root@192.168.1.1:/www/veci/js/pages/cellular.js "$env:USERPROFILE\Downloads\veci-cellular-WE5927-live.js"
```

Review the file for secrets before sharing it in a project chat. No
modem commands or firmware changes are needed for this collection.
