# Guest voucher hotspot v1

This feature adds an isolated guest SSID with time-limited voucher authentication without turning the WE5927 into a heavy RADIUS/SQL appliance.

## Goals

- Keep the existing private SSID unchanged.
- Add a separate `WIFI-Alpha-Guest` network.
- Guest clients cannot reach the private LAN, router administration pages, or each other.
- Captive portal authentication uses a username and password.
- Voucher duration starts on first successful login.
- Presets: 1, 2 and 3 hours.
- Default: one device per voucher.
- Expired vouchers stop authenticating automatically.
- Reboot must not grant a fresh full duration to an already-started voucher.
- Keep RAM and flash use appropriate for MT7628 / 64 MB RAM / 8 MB NOR.

## Architecture

guest Wi-Fi client -> WIFI-Alpha-Guest -> guest/br-guest -> openNDS captive portal -> voucher verifier -> Internet/LTE

openNDS remains responsible for captive-portal interception, client sessions and timeout enforcement. The project-specific voucher layer is responsible only for credential validation, first-login activation, expiry, device limits and LuCI/CLI management.

## Why openNDS

openNDS is a small nftables-based captive portal available for OpenWrt and supports per-client session timeout/quota overrides through BinAuth. Its default BinAuth also maintains the authenticated-client database used for restoring sessions after an openNDS restart.

Do not replace the stock `binauth_log.sh` directly. The implementation should hook the supported `custombinauth.sh` path so openNDS auth-restore behavior is retained.

## Network isolation

Planned network:

- private: existing `lan`
- guest interface: `guest`
- guest IPv4: `192.168.20.1/24`
- DHCP pool: `192.168.20.100-199`
- guest -> WAN/LTE: allowed
- guest -> LAN: blocked
- guest -> router management: blocked except services needed for DHCP/DNS/captive portal
- wireless client isolation: enabled

The feature must never silently convert the private SSID into a captive portal.

## Voucher record

Persistent voucher metadata stays small: username, salted password hash, duration, maximum devices, first-login epoch, expiry epoch, and state.

Plain-text passwords are displayed only when a voucher is created. They are not stored persistently.

Active openNDS session state belongs in tmpfs. Voucher activation/expiry metadata remains persistent so a reboot cannot reset the timer.

## First-login semantics

Example for a two-hour voucher: created 08:00, first login 14:10, expires 16:10. An unused voucher therefore does not lose time while sitting in the voucher list.

## Safety defaults

The package is staged disabled by default during development.

Installing/building the package must not expose an open guest SSID automatically, alter the private Wi-Fi key, alter LTE recovery, replace the default openNDS BinAuth and lose auth restore, allow guest access to LuCI/SSH, or store voucher passwords in plaintext.

## v1 CLI target

- `we5927-voucher create 1h`
- `we5927-voucher create 2h`
- `we5927-voucher create 3h`
- `we5927-voucher list`
- `we5927-voucher active`
- `we5927-voucher disable USER`
- `we5927-voucher extend USER 1h`

## v1 LuCI target

- Dashboard
- Active Users
- Create Voucher
- Voucher List
- Settings

## Validation gate before live deployment

1. Build package against the same OpenWrt 25.12.5 tree as the tested firmware.
2. Confirm image size still fits the 8 MB NOR layout.
3. Verify guest firewall isolation before enabling Internet access.
4. Verify a 1-hour test voucher starts its clock only on first authentication.
5. Verify wrong credentials remain captive.
6. Verify a second device is rejected when max_devices=1.
7. Verify expiry deauthenticates the client.
8. Restart openNDS and verify the remaining session is restored.
9. Reboot the router and verify voucher expiry is not reset.
10. Verify private Wi-Fi, LTE recovery and LuCI remain unaffected.

Until these checks pass, the feature stays a development feature and is not included in the public stable image.
