# VeCI General / VeCI Indonesia firmware profiles — XL quota v0.1

## Two distinct firmware distributions

**VeCI General** is universal, does not install any Indonesia carrier package, and does not display regional quota cards.

**VeCI Indonesia** installs `veci-indonesia-quota`, provides a read-only XL quota card on the home dashboard, and is the extension point for future providers (Telkomsel, Indosat/IM3, Tri, Smartfren, by.U, AXIS and others). Other operators are **not currently integrated**. Edition selection must be explicit; neither edition requires a modem IMEI change.

The workflow `.github/workflows/veci-editions.yml` is manually dispatched from the `feat/indonesia-edition` development branch. It builds two separate firmware images and two matched ABI app feeds from the same pinned OpenWrt/VeCI sources, but with distinct package selections and embedded edition identity:

| Edition | Firmware GitHub artifact | App feed artifact | Quota module |
|---|---|---|---|
| General | `veci-we5927-general-firmware` | `veci-we5927-general-app-feed` | Excluded |
| Indonesia | `veci-we5927-indonesia-firmware` | `veci-we5927-indonesia-app-feed` | Included |

Artifacts include `EDITION.txt`, `SOURCE-COMMIT.txt`, and `VECI-COMMIT.txt`. Matching, cryptographic checksums and kernel ABI are mandatory. Candidate images are **not production releases**.

## Why XL account access is off-router

WE5927 uses `mipsel_24kc`, has limited flash/RAM and uses APKv3 on OpenWrt 25.12. BITS-XL needs Python + pycryptodome; EnQuota distributes x86/ARM64 binaries, not MIPS binaries. Installing these heavy clients on the router would waste scarce resources and can jeopardize connectivity.

Instead:
- XL authentication and refresh-token storage stay on a private server under the SIM owner's control.
- The router stores only a sanitized **memory-only** cache (never the phone number, IMEI, SMS OTP, API key, refresh token or payment credentials).
- The `veci.indonesia status` rpcd method is read-only and requires an authenticated VeCI session. It shows disconnected until genuine, validated data arrives.
- The router's root-only `veci-quota-import` command accepts an extremely small JSON schema over stdin, validates size/operator/nonnegative byte amounts and writes `/tmp/veci-indonesia-quota.json` atomically with mode 0600. It is NOT exposed as an HTTP API or an ubus write operation.
- Quota becomes stale after six hours; does not claim the counter is modem traffic. No purchases or auto top-ups.

## Source projects audited, not bundled

- [BITS-XL](https://github.com/Banten-IT-Solutions/BITS-XL) (MIT): LuCI/MyXL integration, Python 3 backend; offers `bitsxl json quota` and `quotas[].benefits[]` including numeric total, remaining and DATA type.
- [EnQuota](https://github.com/Najihh/EnQuota): multi-provider TypeScript/MCP integration, but XL `QuotaItem` mostly offers formatted remaining values, not a consistently numeric total, so **do not invent the missing quota total**.
- [Ah-Si-Ata](https://github.com/bitscoid/Ah-Si-Ata) (MIT): MyXL Python client with advanced encrypted API support. Also too heavy for router.
- These clients call unofficial/reverse-engineered interfaces which may change and may have provider usage conditions. **No embedded third-party auth keys, default secrets, financial operations or payment features are distributed in this firmware.** Live API success is not yet verified.

## Read-only XL data contract

The external service must authenticate with user consent, fetch actual XL quota, then produce exactly this normalized structure:

```json
{
  "operator": "xl",
  "total_bytes": 10737418240,
  "remaining_bytes": 5368709120,
  "expires_at": 1893456000
}
```

These values are SCHEMA EXAMPLES, not the user's actual quota. Byte totals MUST come from operator quota benefits, not estimated from the router's WAN traffic. `expires_at` is a Unix timestamp (seconds). For example, BITS-XL JSON can be converted using `python3 scripts/veci_xl_quota_normalize.py` running on the separate host. This parser sums only `benefits[].data_type == "DATA"`, skips unlimited benefits, validates remaining/total, requires an expiry, and strips all PII. It uses only Python standard library.

**Important:** `bitsxl json quota` can expose account personal details. Do not post its raw output in GitHub logs, public chat or CI. Keep tokens and OTP entirely on the separate host. The user must complete MyXL login themselves, and the private host-to-router transport must be authorized and secured before enabling automatic updates. There is no publicly accessible quota-import endpoint.

The example importer accepts real quota only after an approved host-to-router connection has been configured. It deliberately cannot log in to XL by itself. On reboot the memory cache clears and UI shows `Belum terhubung` until it is refreshed.

## Optional host sync after MyXL authentication (NOT enabled yet)

After the owner explicitly authorizes a separate, recoverable TEST router and configures their XL session on a trusted Linux host, `scripts/sync_xl_quota_host.sh` can pull BITS-XL `json quota` responses, normalize the numbers and send only that minimal JSON through SSH to `/usr/sbin/veci-quota-import`. It never flashes, reboots, or edits modem identity.

The service templates `examples/veci-xl-quota-bridge.service` and `examples/veci-xl-quota-bridge.timer` target a dedicated least-privilege `veciquota` Linux account, with the BITS-XL login and SSH identities provisioned under that account. Configure an explicit trusted SSH target in `/etc/veci-indonesia/bridge.env` as `VECI_ROUTER_SSH=approved-test-router-host-alias`; SSH host keys must be verified ahead of time, with batch authentication and no new host-key acceptance at runtime. Use an authorized forced-command SSH key for the import only when possible. The `/opt/veci-indonesia` path in the provided systemd unit is a **template**, not an existing installation.

The timer requests quota roughly every three hours, and after a reboot the router cache is intentionally empty until the first successful sync. Rate limits, API changes and authentication expiry must surface as `Belum terhubung` / `Data lama`. Do not disclose the raw MyXL response, SMS OTP, account tokens, phone number or private SSH key in logs or public issue reports.

Deployment on the current live WE5927 is **not authorized**. First finish the candidate firmware build, rerun J9/J9B, and complete controlled test-router UAT. The helper does not itself solve MyXL authentication and has not made a live operator API call.

## Security and future operator architecture

Use per-operator adapters which all return the same normalized quota model, with separate credential stores and TLS rules on the external host. Put only read-only summaries into the VeCI dashboard. In future offer per-operator package breakdown, unlimited/FUP flags and appropriate subquota classification (national, local, application) rather than deceptively combining them.

Never bundle any personal MSISDN or credential in a public image. Use authorized and legally permitted APIs whenever possible; provide an explicit opt-in for unofficial integrations. If a carrier's API cannot legally or reliably be queried, present `Tidak tersedia` rather than synthetic data.

## Acceptance and release gates

- Development static CI must pass; both general and Indonesia candidate images must build to distinct artifacts and pass J9, APK signature and J9B and verify firmware package selections.
- Live XL OTP/session handling, actual numeric quota mapping, refresh expiration, security, and offline fallback still require tests on an authorized private host.
- ALL five Router Apps, native updater, firmware compatibility and device recovery must pass on an approved separate test WE5927.
- **Existing live WE5927 stays unchanged. NO flash, reboot, configuration changes or app installs without explicit owner approval.**
