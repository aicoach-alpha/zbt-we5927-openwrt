# WE5927 SMS Inbox v1.3.1 — read-only effective permissions audit

Date: October 13, 2026. Only metadata Inbox is physically LIVE/PASS.

## Issue

- The live RPC `veci.sms.listIndex` is published under the **write** grant of `veci-sms-inbox-we5927` ACL.
- OpenWrt `rpcd` grants ACL roles via per-login `list read` and `list write` options in `/etc/config/rpcd`. A login with `list write '*'` gets write access to all ACL groups. A plugin's `id -u=0` proves only that rpcd runs as root, **not** that the authenticated browser account is root.
- The physical owner demonstrated allowed access with the currently logged-in session, but **non-admin session denial is still not physically verified**.
- The browser checkbox and second confirmation protect accidental operations but are not substitutes for the session ACL.

Upstream sources: https://openwrt.org/docs/techref/ubus and https://openwrt.org/docs/guide-developer/ubus/session and https://lists.openwrt.org/pipermail/openwrt-devel/2015-September/010241.html.

## New diagnostic

`scripts/veci-sms-acl-session-audit-20261013.sh` is a single-run BusyBox/OpenWrt shell audit. It:

- Verifies it is on the real WE5927 and that the `veci.sms` RPC exists.
- Reads **only** the login section types and read/write ACL group grants using UCI (never reads `.password`, never prints usernames/password hashes or session tokens).
- Prints per-login-category classifications `wildcard`, `explicit_sms_write`, `restricted`, or `needs_manual_review` and corresponding totals (login index only; no user identifiers).
- Uses `ubus call session access` for the standard all-zero unauthenticated session to query whether `veci.sms.listIndex` would be authorized, without executing that method.
- Explicitly declares `NON_ADMIN_SESSION_TEST=not_performed`, because an anonymous denial does not establish denial for every non-admin account. Classifications are static indicators rather than authoritative per-session proof.
- Does NOT issue AT queries, `veci.sms.listIndex`, `veci.cellular.messagingStorage`, perform `session.login` / `session.grant`, modify configuration, restart rpcd, or affect LTE.

## Physical operator step — read-only, no credentials

Use office Windows SSH connection to real WE5927 only:

```sh
cd /tmp
wget -O veci-sms-acl-audit.sh \
  https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/49e510f229e93254729582473c9b5bb10b8b9d0e/scripts/veci-sms-acl-session-audit-20261013.sh
sh -n veci-sms-acl-audit.sh && sh veci-sms-acl-audit.sh
```

Check `SMS_RPC=registered`, `ACL_LISTINDEX_WRITE_DECLARED=true`, and `ANONYMOUS_SMS_LIST_ACCESS=denied`. If access is `ALLOWED_SECURITY_FAILURE`, **STOP** using Inbox, but preserve the live v1.3.1 installation for ACL remediation. Do not run another real SMS listing merely to check the ACL.

## Offline results

- CI PASS **394/394**: https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38337712489
- The six additional mocked ACL audit tests cover permission categories and unusual grants, true/false anonymous access response, wrong board, no password/session-token output, no modem access.
- Existing v1.3.1 physical deployment, 5-slot metadata listing, LTE and backups unchanged.

## Pending authorization gate before single-message content feature

After read-only report, confirm a real least-privileged user session denied using a separate account and a `session access` query. **Do not send any live session token or password in a chat.** Do not create test logins or modify `/etc/config/rpcd` automatically. An administrative user must review effective account grants first. Only then implement a separate `readSlot` ACL and per-message consent with opened-FD modem identity attestation.
