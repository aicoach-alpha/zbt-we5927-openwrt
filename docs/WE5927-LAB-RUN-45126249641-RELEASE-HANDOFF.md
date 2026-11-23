# VeCI v2 WE5927-2SIM — laboratory build 45126249641 release handoff

Date: 2026-11-23 UTC. **NOT APPROVED FOR FLASH.**

## Immutable provenance
- Run: https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/45126249641
- Workflow: `.github/workflows/veci-v2-lab-image.yml`
- Branch: `development/we2825-all13-integration-20261123`
- Commit: `2bb593a133261de0fc2cd5e78e61f574ea1137d4`
- Run conclusion: **success**, job `full-laboratory-image` **success**.
- Artifact ID: `14799062370`; name `veci-v2-we5927-2sim-unsigned-2bb593a133261de0fc2cd5e78e61f574ea1137d4`; expires 2026-12-07 07:45:59 UTC.
- Archive size: `5845972` bytes; archive SHA-256 `d22edfa9eb5dfe3123bbf2a28c4fa4c9cdbbb15e0ac15e7e8da86d868868efcf`.
- Image name: `openwrt-25.12.6-veci-v2-WE5927-2SIM-UNSIGNED.bin`.
- **Image** SHA-256 (different from ZIP): `fe74330808864b1591b481e7d6cd2fb6dfc2b94b97a8c1a2e9a682d02f04ca53`.
- Target `ramips/mt76x8`, supported board `zbtlink,zbt-we5927`; OpenWrt `25.12.6`.

## Verified by this specific CI run
- Native source tests and OpenWrt compilation succeeded.
- Embedded SquashFS/metadata and 40 core ROM payloads verified (`checked_files=54`).
- No-LuCI/core components checks, including exact embedded rpcd and required drivers, passed.
- Explicitly unsigned portable candidate and verification evidence uploaded.

## Mandatory next gates — fail closed
1. Obtain artifact and recompute both ZIP and BIN SHA-256; inspect `VERIFICATION_REPORT.json`, SHA256SUMS and release manifest against **this exact SHA**, not a past build.
2. Verify all required features, not just 40 file presences: actual native UI/rpcd operations, MT7603 AP, Ethernet LAN/WAN, LTE RNDIS with IP and default route, DNS, real SMS, Data Meter, no LuCI, and failure recovery.
3. Trusted **offline** signing with the intended device trust anchor; verify signature on the final byte-identical candidate. Never upload a private signing key into GitHub Actions.
4. Prove target router identity, partition layout and current factory recovery path using read-only evidence. Preserve OEM backup. Do not assume this CI's board name proves physical compatibility.
5. Perform `sysupgrade -T` against the exact signed image **on the target device**, over wired management, then record result and compatibility logs before considering flash. Do not bypass a failed gate or use force.
6. Plan safe recovery for the user's single physical router; perform controlled hardware tests only with explicit flash authorization. Follow with LTE, Wi-Fi, LAN, SMS and 72-hour stability evidence.

## Explicitly NOT established
- No trusted signature or router trust-anchor match; no device-side `sysupgrade -T`.
- No real modem/Wi-Fi/Ethernet physical tests or 72-hour stability test.
- `EXACT_40_CORE_ROM_PAYLOADS=PASS` verifies packaged content, **not** feature parity or real hardware behavior.

**Flash permission: NO.** Do not rename the unsigned image as signed, publish as production firmware, or deploy it to the router.
