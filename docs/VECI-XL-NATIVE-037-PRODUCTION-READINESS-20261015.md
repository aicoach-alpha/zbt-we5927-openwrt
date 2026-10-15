# VeCI XL Native 0.3.7 — targeted production handoff (15 October 2026)

## Completed in this cycle

- Found previously completed signed 0.3.6 APK, owner-only RPCD backend, and standalone `/veci/xl-account.html` UI; did not reimplement them.
- Fixed an actual account UAT blocker: HTTPS VeCI has a different browser storage origin from HTTP VeCI. The XL account page can now sign in to the router directly over HTTPS using the existing `VeciApi.login` mechanism, validate the session, clear router username/password inputs, and then expose XL OTP controls. Cleartext HTTP still disables login completely. No credentials are logged or copied to GitHub.
- Focused UI/RPC/credential-cleanup CI: PASS https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38713741293
- Incremented optional native package to 0.3.7; signed OpenWrt 25.12.5 ramips/mt76x8 APK and validated exact package manifest. Signed build CI: PASS https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38713921262
- New immutable prerelease https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/tag/veci-xl-native-037-6307ad9f38e1
- Added a **separate**, fail-closed installer, retaining unchanged production Core `veci 0.2.2`, existing Cellular/Quota JS, native rpcd/ACL and config SHA guards. Installer source `scripts/veci-xl-native-037-signed-deploy-20261015.sh`. Modes: `--status` (read-only), `--verify` (read-only), `--install`, `--rollback`. Focused signature/installer CI: PASS https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38714174301

## Signed package evidence

| Asset | SHA256 | Bytes |
|---|---|---:|
| `veci-telco-xl-native-0.3.7-r1.apk` | `045c263790a99ac6aa0856a6167207797d1c19824f8ce59793a6a2351771fde7` | 35,024 |
| `veci-xl-037.pem` | `a01cb8213802ada0a256dfe444bda4011c1ac1dc75dc08c57374730ad8f789ec` | 178 |

## Physical production UAT: not yet authorized as ready

This release has NOT been installed and real operator OTP, identity and quota data are NOT yet confirmed. Fail-closed installer **requires** all of the following BEFORE installation: proper WE5927/OpenWrt build, actual Core 0.2.2 immutable fingerprints, signed APK/PEM integrity, transaction-only package installation, **HTTPS-only router administration**, and locally configured authorized operator integration credential files protected by root permissions. The previous physical UI screenshot used `http://192.168.1.1`, so HTTPS-only status requires physical verification, not guessing. Never disable the HTTP listener or alter the router's web authentication without user approval and a verified HTTPS management path.

Office laptop device `25NBCABA13CF` was listed as connected but the account's Desktop Commander monthly usage gate explicitly blocked remote actions. No physical SSH operation was executed in this cycle; do not claim remote checks succeeded. The router remains untouched.

**Next single production decision:** owner approval to safely migrate web administration to HTTPS-only while retaining a tested recovery path, followed by authorized local XL credential provisioning. Only after those prerequisites are actually satisfied should the user perform one real account-owner OTP→profile→quota UAT. No broad LTE/SMS/firmware retests.

Production UI stays entirely in VeCI and does not create any LuCI UI.

## Physical production update — verified by owner on 15 October 2026

Actual physical WE5927 OpenWrt 25.12.5 console output confirms XL Native **0.3.7 installed and RPC live**:

- `VECI_XL_037_SIGNED_PREFLIGHT=pass`; `VECI_XL_037_INSTALL=pass`.
- `VECI_XL_037_RPC_REGISTRATION=pass`; `VECI_XL_037_RPC=registered`.
- `VECI_XL_037_HTTPS_POLICY=enforced`, `VECI_XL_037_ROUTER_HTTPS_ONLY=pass`.
- `VECI_XL_037_CORE_022_PRESERVED=pass`, `VECI_XL_037_ROLLBACK=available`.
- `VECI_XL_037_LUCI_MODIFIED=false`, `VECI_XL_037_MODEM_SMS_UNCHANGED=true`.
- Actual sanitized `veci.xl status`: `{"https_only":true,"operator_configured":false,"session":"not_connected","quota_status":"read_local_only"}`.
- `VECI_XL_037_ACCOUNT_UAT=blocked_operator_configuration`; `VECI_XL_037_OTP_ACTIONS=disabled`; `VECI_XL_037_OPERATOR_QUOTA=not_authenticated`.

The former paragraph **"Physical production UAT: not yet authorized as ready"** above is a *historical pre-deployment snapshot*, superseded by this physical log for APK/RPC/HTTPS. **Only carrier authentication and real quota remain blocked.** Do not regress the working signed package or Core for this blocker.

### Authentication integration gap

The native XL backend needs independently permitted integration material for two distinct hosts. CIAM OTP transport (`veci-xl-ciam.c`) requires locally protected `basic_auth`, `user_agent`, `fingerprint`, `device_id`, and OTP-signature key `ax_api_sig_key`. Profile/quota crypto and HTTPS (`veci-xl-quota-http.c` and chains) require `xdata_key`, `api_key`, and `signature_secret`. Those are integration/client credentials **in addition to the subscriber's normal SMS OTP**. The current root-only credential directories are not configured, and sending OTP must remain disabled.

An open-source BITS-XL reference implementation describes undocumented app requests and ships its own defaults; that code is not proof of authorization to reuse its application secrets. Do not copy third-party keys into the repository, firmware, chat, logs, or router shell commands. The official XL myXL customer help documents the normal number + SMS/email OTP process, but no public end-user quota API is confirmed from it. Integration credentials must be provisioned through an authorized channel; don't fabricate them, downgrade TLS, fake quota, or initiate unsolicited OTP.

The VeCI-native UI entrypoint has been packaged under `/veci/xl-account.html`; display should state `Not configured` and disable account OTP. No further HTTPS-only migration, Core upgrade, LTE reset, or SMS test is required.
