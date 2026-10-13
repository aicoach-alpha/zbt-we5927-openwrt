# VeCI single-SMS read authorization: verified OpenWrt boundary

2026-10-13 — **SOURCE ONLY / NO PHYSICAL UAT / NO PRIVATE SMS API**

## Upstream source findings

* In OpenWrt `uhttpd/ubus.c`, legacy `/ubus` uses the SID carried in the JSON-RPC parameter to query rpcd `session.access` and, only if permitted, adds `ubus_rpc_session` into the forwarded method arguments. For the `/ubus/call/...` form, uhttpd reads the authorization header, performs the same ACL query and inserts the SID. The forwarded argument name is protected from client injection at the HTTP bridge.
* In `rpcd/ucode.c`, ucode request info includes `request.info.acl.user/group/object` from `struct ubus_request_data.acl`. This is the **Unix/ubusd peer ACL**, not the logged-in LuCI or VeCI browser username, and cannot replace the HTTP SID check.
* `rpcd/plugin.c` executable method stdin contains method arguments only; no automatically attached, authenticated request principal is passed in a separate signed envelope.
* **Risk:** a privileged **direct local ubus client** can itself pass `ubus_rpc_session`. Thus even ucode cannot treat its presence as an incontrovertible HTTP-origin attestation. Root-owned system processes are trusted under the intended device threat model; untrusted local users must not be able to impersonate uhttpd's peer ACL.
* `uhttpd.ubus_noauth` would invalidate ACL assumptions. Device configuration, ucode availability, rpcd/uhttpd peer user, and HTTP session behavior are still to be checked physically with **read-only, redacted commands**.

Upstream references:
- https://github.com/openwrt/uhttpd/blob/master/ubus.c
- https://github.com/openwrt/rpcd/blob/master/ucode.c
- https://github.com/openwrt/rpcd/blob/master/plugin.c
- https://github.com/openwrt/rpcd/blob/master/examples/ucode/example-plugin.uc

## Source-only diagnostic implementation

`source/we5927-lte/src/veci-sms-auth-ubus-preflight.uc` implements a mockable
`veci.sms.auth.audit.probe` API requiring an independently ubusd-supplied
privileged Unix ACL peer, fixed object/method, and exact 0..65535 slot.
It consults `session.access` with a `ubus.defer()` request and returns only
`{ok: boolean, diagnostic_only: true}`. It does **not** output the SID or
access SMS, arm a token, read modem state, return sender, or log OTP.

The file is NOT installed, NOT included in the Makefile, NOT registered in
rpcd and NOT used for the production SMS Inbox metadata path. The value
`ok: true` would show the ACL tuple was accepted in this mock/probe, **not**
prove that a specific browser session was bound to a particular native
process; production code must verify that entry provenance first.

## No-go until completed

1. Confirm router includes `rpcd-mod-ucode` and `uhttpd-mod-ubus`
   without installing additional packages blindly.
2. Read-only confirm `ubus_noauth` disabled, CORS policy understood, and
   which ubusd peer Unix identity uhttpd uses; never copy actual session IDs
   or credentials into chat or CI logs.
3. Prove actual privileged and restricted HTTP sessions have contrasting
   authorization outcomes without invoking SMS commands. Avoid creating
   restricted test users without the owner's approval.
4. If probe contract is viable, design a trusted one-time approval bridge
   to the C capability store; authorization must not consist solely of
   `request.args.ubus_rpc_session`. Also bind to exact slot and modem
   generation and preserve consumed-before-I/O semantics.
5. The existing `veci.sms.listIndex` and SMS Storage remain unchanged.

Do not deploy `veci.sms.private.readSlot` or enable `AT+CMGR` in the
production firmware from this probe.
