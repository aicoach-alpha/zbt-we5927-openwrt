# VeCI XL native app-config provisioning v10

**Status:** importer implemented; **no authentic provider credentials included or available**. Installing the importer does **not** connect an account or yield operator quota.

## Scope
- Runs **only locally as root** on the user's OpenWrt device (office laptop → SSH).
- Does not alter LuCI, LTE, modem, SMS, USSD, or Data Meter.
- Does not send an OTP, fetch quota, disable HTTPS checks, or store credentials in public firmware.
- Compatible with the native VeCI XL package's existing /tmp directories and permissions.
- The V9 Cellular VeCI login UI stays unavailable while `veci.xl status` reports `operator_configured=false`.

## Authorized configuration input contract
Only when valid app-integration credentials have been acquired through a permitted provider mechanism, place eight files within `/tmp/veci-xl-authorized-config` on the **router**, owned by root, with mode 0600 and parent mode 0700:

- `basic_auth`, `user_agent`, `fingerprint`, `device_id`, `ax_api_sig_key`
- `xdata_key` (exactly 32 bytes), `api_key`, `signature_secret`

File contents are opaque secret data. The importer never prints their contents or accepts them in command-line flags. **Do not fill these fields with guesses, copied application secrets, or sample/test data**. No hardcoded credentials, tokens or IMEI are distributed.

## Local actions
- `/usr/libexec/veci-xl-authorized-config-import --status`: check presence of valid private-file layout without reading or displaying credentials.
- `/usr/libexec/veci-xl-authorized-config-import --apply`: verify all eight input files and directory permissions, acquire the existing owner-operation lock, reject any existing target configuration or active session, install safely with rollback on partial failure, and delete supplied secret input files after local commit.

Installation of v10 performs **status only**, not `--apply`. A full import is expressly not attempted until a valid authorized bundle exists. Successful local import still does not prove that endpoint authentication, API signatures, consent, or subscriber quota work.

## Release notes
- No password or token is written to GitHub, VeCI JavaScript, or router logs by the importer.
- Configuration is in /tmp RAM, so it will be lost on reboot by design; do not persist it into firmware or generic backups. This is a provisional, RAM-only integration method pending an authorized provider enrollment process.
- Next substantive integration blocker: verified provider support for third-party consent/authentication and subscriber quota API. Do not misrepresent this importer as carrier activation.
