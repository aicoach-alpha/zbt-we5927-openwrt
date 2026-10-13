# VeCI one-process two-step SMS consent UCODE - staged

State: **source-only**, not packaged, no physical SMS reading, no service restart.
The verified office WE5927 has ucode, rpcd ucode and uhttpd ubus loaded,
CORS and `no_ubusauth` disabled.

`source/we5927-lte/src/veci-sms-private-consent.uc` has a two-method ubus
object `veci.sms.private`. `armRead` requires a selected slot and exact
foreground consent, then checks `session.access` for the sensitive
`readSlot` method. A randomly generated 128-bit nonce comes from the
kernel's `/dev/urandom` (16 bytes); failure is denial. The rpcd VM
maintains one pending approval and binds it to the SID, slot and monotonic
30-second deadline. `readSlot` validates ACL independently, consumes
the pending nonce before comparing SID, slot and token, refuses replay,
and currently replies `physical_read_disabled`, never AT+CMGR or PDU.
No SMS body, sender or OTP is read or stored. Memory allocation is bounded
to one tiny record. Restarting rpcd invalidates approval automatically.

**Trust assumption:** `uhttpd` forwards a validated SID only after
checking the user's ubus ACL. `request.info.acl.user='root'` is a Unix
peer permission rather than browser identity. A privileged direct local
ubus call can provide a SID; root-owned processes are in the trusted
device root boundary, but unknown or non-root peers must be denied.
At this stage the unauthenticated/restricted HTTP session negative UAT
and real ucode runtime compatibility are not yet proven.

Separate, not-installed write-only ACL
`source/we5927-lte/src/veci-sms-private-acl.json` permits only
`armRead`/`readSlot` for explicitly selected privileged roles.
Never add these to public/read grants or existing `veci.sms.listIndex`.
No new daemon or flash-bound capability store required for this ucode path;
the earlier C tmpfs store remains unused.

**Release remains NO_GO** until staged ucode interpreter syntax test,
actual restricted HTTP sessions and verified mock transport integration
are proven. The code intentionally cannot display real SMS at present.
