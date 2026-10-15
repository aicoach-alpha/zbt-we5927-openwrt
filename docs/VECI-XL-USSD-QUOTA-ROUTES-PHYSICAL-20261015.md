# VeCI XL USSD quota pathways — physical findings, 2026-10-15

## Verified physical baseline

Physical owner WE5927 output:
- `VECI_XL_USSD_RPC=registered`
- `VECI_XL_USSD_NATIVE=installed`
- `VECI_XL_USSD_CACHE=installed`
- `VECI_XL_USSD_ACL=present`
- `VECI_XL_037_RPC=registered`
- `VECI_HTTPS_ONLY=pass`

The earlier read-only detector displayed `INTERACTIVE_METHODS=incomplete` and `CACHED_QUOTA_METHOD=missing`. It inspected a *verbose ubus text rendering* and assumed `start`, `reply`, `cancel` in that order, which is not a reliable assertion. The fixed read-only probe instead invokes only the local plugin's declarative `list` action and checks each method independently. It does **not** dial USSD or touch AT.

## User-provided menu route (NOT carrier-verified universal menus)

The owner's active XL SIM currently has two reported quota inquiry paths:

- `*808#` followed by `7`, `3`, `2`, `2`.
- `*808#` followed by `7`, `3`, `2`, `1`.

They are user observations, **not** verified as fixed universal code sequences. XL's own September 2026 documentation supports `*808#` for quota lookup but tells users to navigate the menus and select the active plan; the numbered submenu can change by subscriber/plan. Source: https://www.xl.co.id/blog/cek-kuota-xl-paling-mudah-ada-yang-baru-lewat-dial-number

The existing native worker `veci-xl-ussd-once` accepts only literal `*808#` for the initial dial and one- or two-digit menu replies afterward. It deliberately **rejects concatenated codes** such as `*808*7*3*2*1#`, so do not claim direct-dial shortcuts are already supported. Its wrapper limits user-initiated replies to six steps, protects modem exclusivity, and never retries an uncertain outcome.

## Safe follow-up requirements

1. Keep VeCI Core 0.2.2 and XL Native 0.3.7 unmodified; do not change LuCI.
2. In the current VeCI Cellular USSD UI, enter choices *only as they are shown in the actual received operator menus*. For this SIM, the known path is 7→3→2→1 or 7→3→2→2.
3. Do **not** silently send an unverified fixed branch. Each menu selection remains individually user-confirmed; abort if menu text is different or indicates charges, purchases or activation.
4. Show quota only if the received response explicitly provides a reliable remaining quota; no fabricated totals. Keep local cache ephemeral.
5. A future optional guide can prefill the expected next number after checking each operator response. It must not auto-send a chain or bypass the existing carrier safety guard. Release in VeCI with signed provenance and rollback, not as a LuCI modification.
6. Subscriber identity, OTP, package keys and carrier menu response text must not be logged to GitHub.

`USSD operator actual quota success`: **not yet observed**. Native RPC availability is not evidence that the operator returned quota.

## Optional VeCI-only guided page prepared (not yet on physical router)

Two standalone VeCI files `xl-ussd-guide.html` and `xl-ussd-guide.js` implement the observed 7→3→2→1 and 7→3→2→2 menu hints. They use the existing authenticated `veci.ussd` RPC; each `start` and `reply` is a separate user-confirmed action, never an automatic loop. The actual operator text is displayed only in transient DOM and is not written to disk or logged. No new service/API keys or altered modem binaries are needed.

Focused UI CI PASS: https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38723959879.

An optional **SHA256-pinned two-file static installer** was created: `scripts/veci-xl-ussd-guided-static-deploy-20261015.sh`. It adds only previously absent `/www/veci/xl-ussd-guide.html` and `/www/veci/xl-ussd-guide.js`, verifies original Core 0.2.2 fingerprints, both existing XL RPCs, installed XL Native 0.3.7, HTTPS-only, original source commit and SHA256 before install. No package changes, no rpcd restart, no unsolicited USSD. Rollback removes only the two files if byte-for-byte matches. It does not claim a new APK signature: this is a checksum-pinned additive static asset overlay.

Pinned file commit `b412695a088d8cd625b3231f60b8d1fd49d9483c`.
- HTML SHA256: `7878226966d40fbdeea0daab66088660a29c0f5a396b61a5675681594cb84023`
- JS SHA256: `7fe4df1ee56cf64fdc1d04239ee59ffc29b09db3deb51a0b2b657049201874b4`
- Install gate CI PASS: https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38724752584

The optional guide must not be reported LIVE until the owner installs it and confirms it opens in VeCI. It cannot bypass per-selection confirmations or guarantee a fixed carrier menu. A carrier quota display also requires an actual operator response, not merely a successful file install.


## Physical guide UAT and diagnostic follow-up (owner screenshot, Oct 15)

Owner reported:
- \`VECI_XL_GUIDE_SHA256=pass\`
- \`VECI_XL_GUIDE_INSTALL=pass\`
- \`VECI_XL_GUIDE_CORE_PRESERVED=pass\`
- \`VECI_XL_GUIDE=installed\`, modem calls by installer \`false\`.

The owner opened \`/veci/xl-ussd-guide.html\` and saw both route buttons. After pressing a route, the page only reported the generic text “USSD gagal, sesi kedaluwarsa, atau hasilnya tidak pasti”. This proves UI installed and an operation was attempted, **not** that the operator returned any quota. Root cause still unknown.

A genuine guide bug was found: the UI discarded \`result.reason\` on \`ok:false\` in \`begin()\` and used a general \`catch\` for all other failures. The script now maps only a strict allowlist of non-sensitive RPC reasons to human-readable feedback. No automatically repeated USSD. Source UI diagnostic CI PASS: https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38725840722.

A read-only physical root-cause script, \`scripts/veci-xl-ussd-failure-rootcause-readonly-20261015.sh\`, checks registration, method manifest, executability/dependencies, modem USB path/IDs, and sanitized \`we5927-lte status-fast\` SIM/operator guard. It does not send any USSD or print IMEI, phone number or raw operator text. A checksum-pinned one-JS-file update \`scripts/veci-xl-ussd-guide-diagnostic-update-20261015.sh\` preserves the signed Core and XL 0.3.7, verifies old/new SHA256, and backs up only the optional guide JS for rollback. Overlay CI PASS: https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38726102723.

**Neither follow-up is yet physically executed at time of documentation.** Do not claim real *808# quota PASS without the operator response and verified local cache. If the sanitized preflight flags unexpected USB interface, SIM or operator label, investigate those actual physical guard checks before any next USSD request; do not weaken them speculatively.


## Browser RPC status diagnosis (actual screenshot) — 15 Oct 2026

Screenshot from owner's physical VeCI guided page:
\`VeCI RPC: reachable | USSD status RPC: reachable | Izin start: unknown\`.

These observations establish authenticated read access to \`veci.xl.status\` and \`veci.ussd.quotaStatus\`; they **do not** demonstrate either USSD start permission denial or a carrier failure. The two guided routes share the exact \`veci.ussd.start\` call before any menu choices; their identical failure cannot be attributed to the divergent final 1/2 selection.

Exact signed Core's \`VeciApi\` source: upstream repo \`aicoach-alpha/veci\` commit \`bdf7bcf332c23b625e92fb1e00d1fb30edea88b6\`, path \`veci/js/lib/api.js\`. \`VeciApi.call()\` **throws** for any nonzero ubus numeric status (\`error.ubusStatus = status\`); it also throws a sanitized method-specific timeout. Old optional XL guide swallowed all thrown exceptions as generic "RPC, permission, connection" errors. On the browser's \`session.access\` probe it reported \`unknown\` for any exception or unexpected response, making ACL diagnosis inconclusive.

Focused patch now exposes ONLY finite, safe \`ubus_status_N\`, \`request_timeout\`, \`http_4xx\`, \`http_5xx\`, \`session_not_authenticated\`, \`transport_unknown\` categories, not raw exception contents or session IDs. For permission probe it distinguishes \`allowed\`, \`denied\`, \`no_access_field\`, and categorized errors, including string booleans; no USSD sent by the permission probe. This is a one-file optional UI replacement, not a Core/ACL/modem change.

- Browser classifier tests CI PASS: https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38730634176
- One-file rollback/pin deploy gate CI PASS: https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38730885663
- Installer: \`scripts/veci-xl-ussd-ubus-error-update-20261015.sh\`
- Source file sha256 (new): \`342c54d8519aec3b24ab4c1e7ae5bc1bb18c744297520217da216b5db401701e\`
- Expected physical installed previous sha256: \`c60d80b33cd3f49e25ff36ca4801c3ba481244ef2f98bf3697ec19ead61e8d83\`

At report time the new patch is **GitHub CI PASS, not yet physically installed**. Install only after its SHA-pinned guard verifies exact previous JS and Core. Next use **read-only access checker** first; then only one explicitly user-approved \`*808#\` if necessary. No change to live Core 0.2.2, XL Native 0.3.7, LuCI or SMS.
