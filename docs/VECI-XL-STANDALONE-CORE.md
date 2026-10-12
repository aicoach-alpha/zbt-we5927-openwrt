# XL Standalone Stage 1 — On-router quota status core

Status: **LOCAL CACHE / CONTRACT TESTED**, **MyXL authentication NOT IMPLEMENTED**, **real operator quota NOT VERIFIED**, **LIVE ROUTER UNTOUCHED**.

## What is implemented

- `veci-telco-indonesia` is an optional package; General does not include it.
- `veci.quota status` invokes **only** `/usr/libexec/veci-quota-cache status /tmp/veci-telco/quota-xl.json`. No RPC input controls the file path.
- The cache reader is POSIX shell with BusyBox `ls`, `awk`, `wc`, `id`, `date`, `tr`, `grep` and OpenWrt `jsonfilter`. **No Python, Node, coreutils-stat or separate daemon**.
- Its cache lives in RAM under `/tmp/veci-telco`, owned by the executing user (root in rpcd), directory mode **0700**, file mode **0600**, regular files only; symbolic links are rejected. File size must be at most **4096 bytes**.
- Canonical fields: schema=1; provider=xl; state=ready; source=carrier_authenticated; total_bytes and remaining_bytes are nonnegative canonical decimal values, each 13 digits maximum; fetched_epoch is a bounded UNIX epoch timestamp. Numeric input from `jsonfilter` is validated as decimal text; typed JSON authentication must occur at the **producer**. Extra fields (phone numbers, cookies, credentials, headers) are never echoed back.
- Status with no file is `not_connected`; bad format, wrong ownership/mode, source, provider or future time is `unavailable`; readings older than **1800 seconds** are `stale` with **NULL**, not a misleading last known numeric balance.
- The reader returns normalized JSON only. Bucket calculations, FUP/unlimited treatment and timestamps beyond UTC strings will be implemented in a future carrier-specific producer.
- There is NO cache writer in this package yet, specifically to prevent a placeholder or unauthenticated client from pretending to supply official XL data.

## Operator integration boundary

The next local producer should:

1. Be explicitly enabled by the router administrator. Initiate OTP only after informed user action, and keep the OTP out of logs and cache. A normal Home status poll must not send SMS, initiate login, or perform HTTPS.
2. Access the carrier **directly** over verified HTTPS; confirm exact host, endpoint and redirect policy against a legally authorized/maintained integration. Never ship copied proprietary client secrets or an insecure TLS option. No dev server or proxy.
3. Keep carrier tokens in a separate root-only session directory, never in the quota cache. Erase on logout; enforce expiry and backoff on rate limits.
4. Validate each carrier quota response **with types**, verify it is tied to the selected subscriber, prevent aggregation of overlapping buckets and generate an atomic root-owned 0600 normalized cache file. Stale/unavailable must fail closed.
5. Keep a single shared transport/client, retry scheduler and cache normalizer on device. Do not spawn one daemon per operator.
6. Benchmark memory and flash under MIPS `mipsel_24kc` and real `jsonfilter`/BusyBox. The CI tests use an Ubuntu-only fake `jsonfilter` to verify shell safety; they do not substitute for native MIPS compatibility testing.

## Audits and CI

- `tests/test_veci_indonesia_contract.py`: 9 unit tests, including General/Indonesia source isolation.
- `tests/test_veci_quota_cache.py`: 12 negative/privacy tests with a stand-in `jsonfilter`.
- `.github/workflows/veci-indonesia-contract.yml`: sources above, both edition staging, no real operator request.
- Integration into the official Web UI is source-only until the VeCI Core pin contains the latest optional Home card fix and Indonesia firmware is built and tested.

This is **not** a working MyXL login or public release. Never flash the live WE5927, install the J8c package feed on the older kernel, modify a modem identity, or use a developer-hosted intermediary. Future device flashing requires complete Router Apps/updater UAT, rollback, and explicit owner approval.
