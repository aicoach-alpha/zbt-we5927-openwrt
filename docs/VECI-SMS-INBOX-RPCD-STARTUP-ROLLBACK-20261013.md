# WE5927 v1.3 RPC registration failure — post-rollback triage and v1.3.1 staging

Date: 2026-10-13. Device: physical WE5927, office Windows SSH, NOT the home NAS router.

## Observed failure (operator-provided)

Root executed the pinned original v1.3 installer:

```
cd /tmp && sh -n veci-sms-inbox-v13.sh
sh veci-sms-inbox-v13.sh status
sh veci-sms-inbox-v13.sh apply
```

Before apply, exact installed v1.2 Cellular SHA was
`2deb013e6ccf433b9c3abc3d7f02aafb33739dd1b5b5f222d4de501865314d40`,
and no `veci.sms` RPC, worker, ACL or v1.3 backup existed. Available overlay
about 1.7 MiB. After apply: 

```
INBOX_V13_ERROR: rpc_registration_not_visible
INBOX_V13_AUTOMATIC_ROLLBACK_STARTED
```

IMPORTANT: the rollback **started**, but this stdout alone does NOT prove
all target files and rpcd registrations were restored. Do not attempt
another apply before physical read-only inspection.

## Likely but not established root cause

The original v1.3 script called `/etc/init.d/rpcd restart` then checked
`ubus list veci.sms` **immediately**, with zero startup grace period.
OpenWrt's rpcd executable plugin registers its ubus object when its
executable `list` output parses successfully during daemon initialization.
This object may not exist yet when procd returns from the restart request.
Other possibilities: plugin registration / script execution failure.
Do not conclude startup race until on-device data confirms it.

Official OpenWrt rpcd documentation:
https://openwrt.org/docs/techref/rpcd

## Read-only physical checks FIRST

Run on the **actual** root WE5927 SSH session; no AT/modem calls:

```sh
sh /tmp/veci-sms-inbox-v13.sh status
printf 'BACKUP v13 SHA: '; sha256sum /root/veci-sms-inbox-v13-rollback/cellular-v12.js 2>/dev/null || echo backup_not_found
printf 'RPC plugin registration:\n'; ubus list veci.cellular; ubus list veci.sms
printf 'Current plugin files:\n'; ls -l /usr/libexec/rpcd/veci.sms /usr/libexec/veci-sms-inbox-index /usr/share/rpcd/acl.d/veci-sms-inbox-we5927.json 2>/dev/null || :
```

Expected recovered UI SHA v1.2 above and `veci.sms` absent. The saved
`/root/veci-sms-inbox-v13-rollback` may remain even after the failed
installation; do not delete it until health has been verified. A missing
v1.3 plugin under `ubus list` is expected after rollback. Existing
`veci.cellular` should remain registered.

## Corrected v1.3.1 implementation — not applied

Staged source: `scripts/veci-sms-inbox-admin-ui-v131-install.sh`.
This uses same four v1.3 payload hashes, but a new isolated backup path
`/root/veci-sms-inbox-v131-rollback` to avoid overwriting prior evidence.
It checks preexisting `veci.cellular` ubus registration, parses the new
plugin's `list` signature before ANY install, and after a single rpcd
restart retries read-only presence of both objects for up to **12 seconds**.
It also verifies rollback file hashes and absence of installed RPC/worker/ACL
and emits `INBOX_V131_ROLLBACK_FILES_PASS` when restored.
It does not invoke `listIndex` in the installer and sends **no** modem AT.

Status: **384/384 host regression PASS** including fake rpcd slow startup,
no startup registration, safe rollback and no-existing-cellular abort.
https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38335670579

**Deployment HOLD:** do not deploy v1.3.1 until read-only physical v1.2
rollback evidence and `veci.cellular` registration are received.
Never force-delete existing router files or run `AT+CMGL=4` during triage.
