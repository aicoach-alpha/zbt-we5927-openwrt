# VeCI private single SMS UI v1.4 — SOURCE-ONLY / NO DEPLOY

This is a separate v1.4 page candidate. Existing SMS metadata v1.3.1
remains byte-for-byte unchanged, including its pinned SHA installer and
rollback copies. The v1.4 page is **not** referenced from the active
firmware/package or installer.

Only a user-triggered metadata listing makes the new panel visible.
The user selects an actual listed index, checks a private-read box,
confirms the explicit modal, and the foreground handler calls
`veci.sms.private.armRead` then `readSlot` with the nonce only in local
JS memory. No auto SMS read, no background polling, no browser storage.
Any actual body would be rendered only through textContent, then cleared
after 30 seconds. Unauthorized/unavailable results expose no private text.

Current backend deliberately always returns
`physical_read_disabled`, so no real SMS text is displayed. This
implementation is an end-to-end browser/API **staging contract**, not a
claim that the feature is live.

Block deployment until HTTP restricted user UAT, modem generation
handling, verified and safe CMGR transport, and physical consent testing.
