# VeCI auth backend physical readiness (read-only)

This is an optional **non-installing** owner-run diagnostic for the **office
WE5927 only**, connected to the user's Windows office laptop at
`root@192.168.1.1`. The NAS at that same IP has a different ZTE device.
Do not run it there.

File: `scripts/veci-sms-auth-backend-preflight-20261013.sh`.
Source-only: not packaged into firmware and not deployed.

The script observes only whether ucode, rpcd's ucode plugin and uhttpd's
ubus module appear installed; it checks UCI `ubus_noauth` / `ubus_cors`
flags and whether the sensitive private SMS ubus endpoint unexpectedly
exists. It never dumps rpcd logins, password hashes or browser session
tokens. There is **no** modem command, SMS listing, service restart, network
mutation or package installation.

`UHTTPD_UBUS_NOAUTH=enabled` is a **NO-GO** for sensitive SMS RPCs.
`UCODE_BINARY=absent` or `RPCD_UCODE_PLUGIN=absent` means the proposed
ucode path is not available on this router without an explicit change.
`VECI_PRIVATE_SMS_API=registered_UNEXPECTED` is a **STOP/REVIEW** condition,
since the private SMS API is deliberately not shipped.
`UHTTPD_UBUS_CORS=enabled` requires reviewing trusted origins.
`absent_or_alternate_path` is not proof uhttpd-mod-ubus is absent.

**Not performed on physical router as of this stage.** Do not run
this from `andre-nas` or `dell-andre`. Do not assume output of an
offline mock matches physical configuration. Human approval is mandatory
before any physical deployment of readSlot or issuing `AT+CMGR`.
