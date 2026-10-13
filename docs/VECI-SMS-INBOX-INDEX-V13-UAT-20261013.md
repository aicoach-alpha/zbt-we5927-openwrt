# WE5927 VeCI SMS Inbox metadata v1.3 — optional staged partial release

Date: 2026-10-13 (Asia/Jakarta). Scope is metadata index only, not message bodies or send/delete.

## Established LIVE baseline (do not disturb)

- Router WE5927 OpenWrt 25.12.5 physical UI Cellular SMS Storage **LIVE/PASS** on v1.2.
- Actual displayed SMS storage: **5 / 255 (ME)**. LTE data link active and Internet reachable; v1.2 patched Cellular 8352-byte SHA256 `2deb013e6ccf433b9c3abc3d7f02aafb33739dd1b5b5f222d4de501865314d40`.
- V1.2 backup `/root/veci-sms-ui-exact-live-v12-backup` must be preserved, as must SMS v1/v2 diagnostic rollback directories.
- Modem hardware PDU + IRA, CMGL=? support and single root CLI `AT+CMGL=4` **metadata-only** list of five slots indexes 0–4 were physically confirmed earlier. Listing may change unread flags to read; do not auto-run.

## New optional isolated capability

- Package `source/veci-sms-inbox-we5927/` remains *unselected* in default firmware configuration. Provides no daemon. Its installation is explicit only.
- New rpcd exec object `veci.sms` method `listIndex` (not injected into existing `veci.cellular`), with dedicated ubus **write-only ACL**. No read or public ACL grants it.
- Requires exact user-supplied `scope:metadata_only` and `ack_unread_status:I_ACCEPT_UNREAD_TO_READ`; rejects malformed/oversized input before the worker.
- Requires root-run service and a 60-second per-device server-side rate limit even after failed attempts. Separate rpcd lock does not replace existing shared modem AT lock.
- Reuses the exact 5,349-byte root CLI worker already proven on physical modem. Holds modem AT lock for PDU mode check and listing. Fails closed on incomplete/invalid responses, caps AT response at 8192 bytes and 16 entries.
- Parses only numeric slot ID, SMS status and TPDU size. No SMS sender, PDU text, OTP or body may enter the ubus response. An explicit output schema/length gate rejects unexpected worker output.
- UI added on top of the **exact existing v1.2**: separate *SMS Inbox — metadata only* panel. Button is initially disabled. User must check a warning box and then confirm a modal. Each action consumes both approvals; never polls on page load/reconnect/refresh. All modem-derived values rendered with textContent.
- The existing user-clicked `Check stored SMS count` remains unchanged and continues via the existing v2 `messagingStorage` endpoint.

## Device changes when operator chooses apply

- Installer `scripts/veci-sms-inbox-admin-ui-v13-install.sh` is explicit and reversible, with `status|apply|rollback` modes.
- It verifies the physical WE5927 board, root, v1.2 Cellular SHA, absence of existing `veci.sms` files, free overlay and all downloaded payload SHA256 before any writes.
- It installs **only** `/usr/libexec/rpcd/veci.sms`, `/usr/libexec/veci-sms-inbox-index`, `/usr/share/rpcd/acl.d/veci-sms-inbox-we5927.json` and the Cellular UI, with separate `/root/veci-sms-inbox-v13-rollback` backup.
- A single `rpcd` restart is needed to register the new object. This may log the user out of VeCI temporarily. It does not restart LTE, ubus itself, uhttpd or reboot the router.
- Installer verifies `ubus list veci.sms` before reporting LIVE_ASSETS. If registration fails, it automatically restores v1.2 and removes v1.3 files; mocked failure path passed offline CI.
- **Installing does not send any AT command.** The first `AT+CMGL=4` can occur only after the administrator explicitly consents to listing. No SMS is deleted or sent by this code.
- Manual rollback will refuse to overwrite newer UI or RPC files whose SHA changed since installation. Legacy v1/v2/v1.2 backups remain untouched.

## Pinned asset SHA-256 and source

Payload commit: `cecfe43e99a1bf9b4c7c9c1158432acd44099de5`.

| Asset | SHA256 |
|---|---|
| Exact-v1.2-derived v1.3 Cellular | `5f34ca2320a77f0f91d1bda524e84f18c79af1d589ddeb2bf9392c2cd30af6ca` |
| `veci.sms` RPC | `24102a1919856de11a2eb207c57e56b78f85612a50bf71628ff1959edf856a2e` |
| Metadata worker | `ff11a42144181de131f1e595db163bd6f8ce7b3dd718a9e63cdf594e4fe2d7ec` |
| Separate ACL | `8bfe87008b20d8060f07e6ee7058cea1873bc7f39c99a5c58ea22c76b2fd1fa4` |

## Quality gates

- Offline tests **375/375 PASS**, including 9 RPC tests, 8 UI tests, 7 installer tests, native framing/identity tests and previous LIVE v1/v2/v1.2 regressions.
- https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38334825882
- `INERT_BUILD_GUARD_PASS`: native SMS/USSD extensions not linked into firmware.
- Historical initial staging status: no physical v1.3 deployment at creation time. **Superseded by v1.3.1 physical LIVE/PASS acceptance below.**

## Operator procedure: office laptop SSH to actual WE5927

```sh
cd /tmp
wget -O veci-sms-inbox-v13.sh \
  https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/9832b7d7267a0ff6720ee6268d06b5295a84ef79/scripts/veci-sms-inbox-admin-ui-v13-install.sh
sh -n veci-sms-inbox-v13.sh && sh veci-sms-inbox-v13.sh status
sh veci-sms-inbox-v13.sh apply
```

9832b7d7267a0ff6720ee6268d06b5295a84ef79 placeholder is replaced by the exact immutable GitHub commit containing the final script, after CI PASS. Do not run an unpinned URL.

After `VECI_INBOX_V13_ASSETS_PASS`, refresh/login VeCI and click Cellular. Use `SMS Inbox — metadata only` checkbox and second modal ONLY if acknowledging the risk: received unread SMS can be marked read. The operation cannot be undone. Never use this action merely to test whether the UI exists.

Rollback, if required: `sh /tmp/veci-sms-inbox-v13.sh rollback`.

## Not included

- Opening actual SMS text, decoding OTP/sender in browser, sending or deleting SMS.
- Carrier USSD sessions, XL quota balance retrieval, auto menu selection/purchase.
- Firmware flashing, new daemon or network connectivity changes.
- Production-level opened-file-descriptor modem identity check is not yet in the real root CLI (sysfs+path checks occur under lock). Hardware identity and USB hotplug behavior must be UAT'd separately before general distribution.
- UI/ACL and browser role behavior not yet verified on physical hardware. Do not claim full Inbox LIVE until user reports physical UAT.


## Physical WE5927 v1.3.1 acceptance — 2026-10-13

**LIVE/PASS for metadata-only Inbox** (confirmed with operator-owned physical SSH transcript and two dashboard screenshots). Owner first ran the read-only rpcd preflight. Returned `RPCD_PLUGIN_LIST_CONTRACT_PASS`, `SOURCE_SHA_VERIFIED=true`, `NO_MODEM_COMMANDS_SENT=true`, UI v1.2 SHA `2deb013e6ccf433b9c3abc3d7f02aafb33739dd1b5b5f222d4de501865314d40`, `veci.cellular=registered`, `veci.sms=absent`, old failed v1.3 backup valid. Owner then downloaded pinned 8,467-byte v1.3.1 installer from `cfc8007963060d8392387b3952463bf6e5f345aa`, ran status and apply, obtained **`VECI_INBOX_V131_ASSETS_PASS`** and **`MODEM_SMS_NOT_ACCESSED_BY_INSTALLER`**. Output verified all four pinned SHA256 values:

```
Cellular 5f34ca2320a77f0f91d1bda524e84f18c79af1d589ddeb2bf9392c2cd30af6ca
RPC      24102a1919856de11a2eb207c57e56b78f85612a50bf71628ff1959edf856a2e
Worker   ff11a42144181de131f1e595db163bd6f8ce7b3dd718a9e63cdf594e4fe2d7ec
ACL      8bfe87008b20d8060f07e6ee7058cea1873bc7f39c99a5c58ea22c76b2fd1fa4
```

Independent rollback backup `/root/veci-sms-inbox-v131-rollback` is present; retain the older failed v1.3 backup and original v1/v2/v1.2 backups. Overlay went from **380 KiB used / 18%** to **392 KiB used / 19%** (about 12 KiB additional). About 1.7 MiB remained free.

The first screenshot confirms Cellular UI and opt-in warning checkbox are rendered with no list requested, `Data link active`, `Internet: Reachable`, LTE and registered packet service. The second screenshot, following a **deliberate user-authorized UI listing**, confirms **`Listed 5 SMS slot(s)`** with indices 0..4, status 0 and TPDU sizes 163,48,153,163,52 bytes. These match earlier physical CLI evidence. **A real `AT+CMGL=4` occurred at the user's request, and it may change unread flags to read.** Do not re-run merely to verify the UI. No sender, body or OTP was shown.

**Authorization caveat:** The dedicated `veci.sms.listIndex` method is declared under an rpcd `write` ACL. This is **not intrinsically proof of an `admin` role**—actual access is determined by the current session's granted ACLs. The backend runs as root under rpcd, so checking `id -u` does not identify the browser user. Physical browser success proves the currently logged-in session is allowed; **negative authorization from a non-admin session remains unverified**. Before broader use, audit `/etc/config/rpcd` login ACL grants, test a least-privilege session cannot call `veci.sms.listIndex`, and ensure no wildcard permission leaks. Never send login secrets or session tokens in reports.

**Feature status:** SMS storage and manually consented **metadata Inbox are LIVE/PASS**. Read SMS content/sender/OTP, SMS send/delete, and live XL USSD are **NOT LIVE**. Do not infer that `status:0` proves SMS remain unread after listing, nor that reconnect/SIM switching actions were exercised (the buttons remain visibly present).
