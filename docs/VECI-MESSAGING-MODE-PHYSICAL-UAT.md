# WE5927 physical SMS mode + charset preflight — operator step

Date: 2026-10-12. Source-only /tmp diagnostic. Never modifies firmware, LTE, SIM, AT mode or message state.

## Prior proven baseline

On actual WE5927 attached to Windows office laptop (NOT andre-nas):
- Host 192.168.1.1; board zbtlink,zbt-we5927; OpenWrt 25.12.5/kernel 6.12.94.
- Modem USB 05c6:902e with ttyUSB2 on interface 1.4, ttyUSB3 on interface 1.5 (never probe it).
- Persistent veci.cellular messagingCapabilities and messagingStorage LIVE/PASS.
- SMS storage last reported ME used 5 / total 255; no SMS contents retrieved.
- Two persistent rollback backups for existing v1/v2 must remain intact.

## What this preflight adds

The immutable source at commit 3b9478d18f8f5a8c36df63cad17f051ad865643d provides
scripts/veci-messaging-readiness-ondevice.sh.
It requires the known board and validated physical /sys interface and VID/PID.
It obtains the common exclusive we5927-at.lock without waiting or retries.
Only two on-demand AT READ-ONLY queries: AT+CMGF? for current SMS PDU/text mode
and AT+CSCS? for active modem terminal character set. The shell script emits
only allowlisted SMS mode and charset labels. Neither query reads SMS contents,
sends SMS, runs USSD, changes configuration or reads OTP.

## Manual operator step — SSH on office router ONLY

cd /tmp
wget -O veci-messaging-readiness.sh \
  https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/3b9478d18f8f5a8c36df63cad17f051ad865643d/scripts/veci-messaging-readiness-ondevice.sh
sh -n veci-messaging-readiness.sh && sh veci-messaging-readiness.sh

Expected shape only (do not fabricate real values):

{"ok":true,"source":"read_only_at","sms_mode":"pdu|text|unknown","charset":"..."}

The actual label comes only from device response. If it reports modem_busy,
do not force/retry automatically. Script performs no persistent mutations.

## Status/next gate

303/303 offline unit tests PASS in GitHub Actions:
https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38224678238
including new strict read-only preflight parsing tests and revised verified
mock transport lock-order tests. Native SMS/USSD transport remains gated
out of the firmware, per INERT_BUILD_GUARD_PASS.

Do not call AT+CMGL or AT+CMGR on the real modem solely for this check:
listing may alter unread flags; message bodies/OTP are sensitive. Real
inbox or XL USSD requires a separate permissioned and rollbackable build
with backend authentication, CSRF, device/session correlation, privacy
and a physical UAT for all edge cases. No automatic menu purchases.
