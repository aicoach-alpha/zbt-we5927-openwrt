# VeCI Generic USSD Dialer — 16 October 2026

## Product correction
USSD is an interactive dial service on the active SIM. It is **not** inherently an XL quota API. The previous VeCI XL-only transport was hard-coded to `*808#` and an XL operator check, which made it unsuitable for a generic router USSD feature. Keep the existing XL quota module unchanged and introduce an optional, independent native VeCI dialer.

## New optional package
- `source/veci-ussd-dialer` — `veci-ussd-dialer` APK 0.1.0.
- Frontend `/veci/ussd-dialer.html`: owner sign-in, free-form bounded USSD code, single-click consent, display actual operator replies, manual numeric response, explicit local session closure.
- RPC `veci.dialer`: read-only `status`; write-only `start`, `reply`, `cancel`. Independent ACL; no raw AT endpoint.
- Worker `veci-ussd-dialer`: verifies real physical WE5927/ttyUSB2/Qualcomm 05c6:902e/SIM slot and uses the pre-existing `we5927-at.lock` and shared prior `/tmp/veci-xl-ussd.session` for mutual exclusion.
- Native `veci-ussd-dialer-once`: bounded `AT+CUSD` only, no `ATD` or `AT+CMGS`, waits for both acknowledgement and asynchronous `+CUSD`; supports full dial strings such as `*123#`, `#21#`, `*808*7*3*2*1#`.
- Input characters strictly `0–9`, `*`, `#`; full code begins with `*` or `#`, ends with `#`, max 32 characters; manual menu reply 0–99.
- HTTPS-only enforced in RPC for all write methods, separate user approval for each transaction, no automation, no dial or reply when page loads, no quota cache writes, no third-party account keys or modem/SMS changes.

## Verification boundaries
- PTY host simulation and source checks: PASS https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38837908400.
- Cross-compiled/signed MIPS release workflow `.github/workflows/veci-generic-ussd-signed.yml`: launched separately, result must be verified before claiming signed package.
- **No generic package has been installed on the physical router; operator USSD response remains unverified.**
- Preserve installed VeCI Core 0.2.2, XL Native 0.3.7, LuCI, SMS, LTE, HTTPS-only, and owner backups.
- Any production installation must verify signed APK and target platform, simulate the apk transaction, then check `veci.dialer` registration and a browser-to-RPC authenticated read-only method before dialing. On failure, remove only the optional package.


## Owner physical UAT update — 16 October 2026

The owner installed 0.1.0 on physical WE5927 and reports:
- \`VECI_GENERIC_USSD_010_SIGNATURE=pass\`, \`SIMULATION=pass\`, \`INSTALL=pass\`.
- \`VECI_GENERIC_USSD_010_RPC=registered\`, \`PACKAGE=installed\`, \`CORE_PRESERVED=pass\`, \`ROLLBACK=available\`.
- Screenshot of \`/veci/ussd-dialer.html\` displays entered \`*808#\` and:
  "USSD gagal: Transaksi gagal atau respons RPC tidak pasti. Tidak ada pengulangan otomatis."
- Therefore **APK/RPC/UI are LIVE but real generic USSD operator transaction has NOT PASSED**. The screenshot does not prove the dial reached the modem.

Offline audit of the exact signed VeCI Core 0.2.2 APK confirmed \`/www/veci/js/lib/api.js\` SHA256 \`61f8c5ca16d23ea29281cd98a37bd16cf79d8610eaf762329863a714ce2090be\`.
The exact API throws \`Error\` with integer \`ubusStatus\` when the JSON-RPC response status is nonzero. The generic USSD frontend originally **swallowed that status**, making permission-denied (code 6), timeout, backend failures indistinguishable. CI source of the exact APK: https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38839621767.

A standalone **read-only** browser probe using \`session.access\` (\`scope=ubus, object=veci.dialer, function=start\`) was added; browser-side HTTP ubus automatically supplies the calling session ID, so do **not** expose or pass explicit \`ubus_rpc_session\` parameter. The UI now displays safe ubus codes and disallows further dial attempts if access explicitly returns false.

Only the **two byte-verified JavaScript versions** are eligible for overlay:
- Previously signed 0.1.0 JS: SHA256 \`1b30bce5c5a52b1485290622f1342470d5f86bd6baacbfc2e37397118051b8e0\`.
- New read-only permission/error UI: SHA256 \`26e43698e48f72ba7c8a256c8f6cb469f803116ad1a92aae939a4bec33e2f304\`.

Installer \`scripts/veci-generic-ussd-browser-acl-diagnostic-20261016.sh\` is a source-SHA-pinned, reversible JS-only overlay, never changes the signed APK, daemon, ACL, original Core, LTE, SMS or HTTPS-only. Focused CI PASS https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38840195175.

**Physical overlay not yet installed as of this note**. After owner installs, inspect \`Izin start\` without dialling any code. If \`denied\`, re-login to refresh session ACL (group permissions are resolved at login), then inspect read-only again; if still denied, inspect effective login \`list write\` roles without broadening access. No speculative chmod, ACL grants, modem restarts, or repeated USSD calls.



## Physical USSD dial UAT: ubus status 5, 16 October 2026

Owner screenshot after user-confirmed \`*808#\`: \`ubus_status_5\`; permission test on same installation had \`Izin start: allowed\`. This rules out assuming an ACL denial (ubus 6). **No real operator response observed.**

Verified upstream OpenWrt \`rpcd/plugin.c\`: \`rpc_plugin_call_finish_cb()\` uses \`UBUS_STATUS_NO_DATA\` for a successful JSON parser state with no result object. Thus 5 is a backend/exec response condition, not a failed credential check and not proof of modem dial success.

A **fake input, zero-modem-transmission** root-cause script is available:
\`scripts/veci-generic-ussd-nodata-readonly-diagnosis-20261016.sh\`.
It first validates SHA256 fingerprints of the exact installed rpcd plugin and shell worker, checks Core and board, and issues only one intentionally impossible dial string \`NOT_A_USSD_DIAL\` to the local direct plugin and to \`ubus\`. The immutable plugin rejects that string before ever invoking the modem worker. Prints only sanitized stage/pass/exit flags, never phone numbers, AT commands or actual modem responses. CI safe-scope PASS https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38842268141. This probe is **not yet physically executed**, and therefore actual NO_DATA root cause still unresolved.

Do not test legitimate USSD again until fake path proves RPC transport or root cause is repaired. Do not reset modem, SMS, LUCI, HTTPS-only, Core, XL 0.3.7, or signed generic dialer based on code 5 alone.
