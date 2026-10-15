# VeCI-only frontend development policy (effective 15 October 2026)

**Non-negotiable product rule:** all user-facing router development for the VeCI project (General and Indonesia editions) must be authored and delivered **inside VeCI**. LuCI is an existing technical/expert access path, never the destination for new or updated features.

## Architecture contract

- **Primary experience:** `aicoach-alpha/veci` — `veci/js/pages/`, shared VeCI components/styles, and authenticated `/ubus` calls. The pinned VeCI core version in the firmware integration repo must be advanced only when existing release-security gates pass.
- **Native backend:** OpenWrt `rpcd`, `ubus`, UCI, and lightweight operator adapters can remain independent and shared. Every new user-facing capability must be integrated into VeCI and tested there.
- **LuCI:** preserve installed legacy/technical administration without feature development. Do not create new `luci-static` pages, `luci-app-*` frontend modules, LuCI menu entries, or new user experiences that link out to LuCI as a substitute for a VeCI page.
- **Existing Indonesia quota v0.2.1:** backend `veci.quota` and its read-only cache stay installed. The already-installed LuCI quota view is a **legacy artifact**, not a new development target. The intended home is **VeCI > Cellular > Operator Data Quota**. Do not reinstall the already-PASS backend merely to move the UI.
- **Do not falsely mark operator data live:** before an authorized and authenticated carrier response, VeCI shows `not_connected` / unavailable, with no invented total or remaining quota.
- **Existing router operations:** do not force firmware flash, reset the modem, or disturb SMS Center. No deployment is proved LIVE without a physical router UI test.

## Continuous enforcement

`scripts/check-veci-only-ui.py` gates new commits against the policy baseline `7319404d54f5fa7b856fee48197f9bbabe99971c`. It rejects any *added or modified* LuCI interface path; removing obsolete LuCI UI files is allowed. This protects the already-deployed historical LuCI files without inviting new LuCI development. The GitHub workflow `.github/workflows/veci-only-ui-policy.yml` runs this check for relevant pushes and pull requests.

There is no user-facing feature-exception path that silently reverts to LuCI. If VeCI integration is blocked, surface the blocker and fix VeCI or its packaging before claiming delivery.
