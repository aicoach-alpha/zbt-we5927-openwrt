# VeCI XL USSD quota pathways — physical findings, 2026-10-15

## Verified physical baseline

Physical owner WE5927 output:
- `VECI_XL_USSD_RPC=registered`
- `VECI_XL_USSD_NATIVE=installed`
- `VECI_XL_USSD_CACHE=installed`
- `VECI_XL_USSD_ACL=present`
- `VECI_XL_037_RPC=registered`
- `VECI_HTTPS_ONLY=pass`

The earlier read-only detector displayed `INTERACTIVE_METHODS=incomplete` and `CACHED_QUOTA_METHOD=missing`. It inspected a *verbose ubus text rendering* and assumed `start`, `reply`, `cancel` in that order, which is not a reliable assertion. The fixed read-only probe instead invokes only the local plugin's declarative `list` action and checks each method independently. It does **not** dial USSD or touch AT.

## User-provided menu route (NOT carrier-verified universal menus)

The owner's active XL SIM currently has two reported quota inquiry paths:

- `*808#` followed by `7`, `3`, `2`, `2`.
- `*808#` followed by `7`, `3`, `2`, `1`.

They are user observations, **not** verified as fixed universal code sequences. XL's own September 2026 documentation supports `*808#` for quota lookup but tells users to navigate the menus and select the active plan; the numbered submenu can change by subscriber/plan. Source: https://www.xl.co.id/blog/cek-kuota-xl-paling-mudah-ada-yang-baru-lewat-dial-number

The existing native worker `veci-xl-ussd-once` accepts only literal `*808#` for the initial dial and one- or two-digit menu replies afterward. It deliberately **rejects concatenated codes** such as `*808*7*3*2*1#`, so do not claim direct-dial shortcuts are already supported. Its wrapper limits user-initiated replies to six steps, protects modem exclusivity, and never retries an uncertain outcome.

## Safe follow-up requirements

1. Keep VeCI Core 0.2.2 and XL Native 0.3.7 unmodified; do not change LuCI.
2. In the current VeCI Cellular USSD UI, enter choices *only as they are shown in the actual received operator menus*. For this SIM, the known path is 7→3→2→1 or 7→3→2→2.
3. Do **not** silently send an unverified fixed branch. Each menu selection remains individually user-confirmed; abort if menu text is different or indicates charges, purchases or activation.
4. Show quota only if the received response explicitly provides a reliable remaining quota; no fabricated totals. Keep local cache ephemeral.
5. A future optional guide can prefill the expected next number after checking each operator response. It must not auto-send a chain or bypass the existing carrier safety guard. Release in VeCI with signed provenance and rollback, not as a LuCI modification.
6. Subscriber identity, OTP, package keys and carrier menu response text must not be logged to GitHub.

`USSD operator actual quota success`: **not yet observed**. Native RPC availability is not evidence that the operator returned quota.
