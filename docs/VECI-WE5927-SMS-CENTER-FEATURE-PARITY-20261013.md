# VeCI WE5927 SMS Center — physical UAT status (14 October 2026)

## Verified LIVE on the owner's physical ZBT WE5927

- SMS feature persistent ON/OFF switch; active SMS Inbox and current modem storage identified as ME.
- SMS Inbox originally displayed five XL SMS segments, joined into three readable messages, with sender, network date/time, read/unread status, and full body.
- Delete SMS **functionally PASS**: user confirmed deleting one multipart SMS (two underlying stored slots), storage count fell from 5 to 3 after a fresh Inbox read.
- Copy Message **functionally PASS** on the user's local HTTP router page.
- SMS Compose/Send **end-to-end LIVE/PASS**: owner submitted an SMS through VeCI v1.5.5, browser reported “Accepted by modem,” **and owner confirmed the recipient device received the message**.
- Admin auth/ACL and SMS feature switch remain in place. No SMS was transmitted during installation.
- Do not re-test previously verified features without a reproducible regression. Existing UI visible in latest UAT is functional but Compose form styling needs polish.

## Deployment evidence / scope

- v1.5.5 installer: `scripts/veci-sms-mifi-v155-send-install.sh`, hotfix commit `4cc2d7537d09d3495d02476ed27f8bb51da529e8` applied by owner.
- Owner reported final installation: `SMS_SEND_V155_BACKEND_AND_UI_LIVE_INSTALL_PASS`, native MIPS binary SHA PASS, anonymous denied, ON/OFF preserved, with zero modem commands during install.
- The original v1.5.5 install attempt failed RPC-registration check and rolled back; subsequent corrected installer succeeded.
- **Reply** UI is present for numeric-originator messages but user has not separately demonstrated a Reply send.
- **Delete from SIM (SM)** is implemented conditionally but not physically verified: observed store was ME.
- Do not claim delivery reports, Sent folder, Drafts, multipart sending, cross-store switching, or USSD are LIVE.

## Next changes — execute as small releasable vertical slices

1. **Sent Messages**: record a bounded, private Sent history only when the modem confirms acceptance. Clearly distinguish accepted-by-modem from received-by-recipient. Make it viewable across VeCI devices, never store message content in logs; preserve ON/OFF.
2. **Drafts**: create/edit/delete persisted private drafts with explicit user actions and reasonable small storage limits. Avoid browser-local storage that leaks across users.
3. **Compose polish**: responsive form layout, clear recipient input, status, character count, actions; Reply only to real phone numbers, not brand names.
4. **Multipart SMS-SUBMIT**: implement proper concatenation UDH, sensible confirmation for the complete message and per-part non-retry handling; physically verify separately.
5. **Sent storage, delivery report, SM/ME memory switching, USSD**: discover modem support before enabling controls; don't infer missing support.

Keep each cycle: implement → focused tests → SHA-pinned reversible deploy → actual device functional verification → next. Never delete existing SMS, change SIM, reboot, flash, or send test messages without direct user action.
