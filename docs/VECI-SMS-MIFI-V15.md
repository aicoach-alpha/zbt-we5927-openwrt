# VeCI SMS MiFi v1.5
User-facing contract:
- SMS ON/OFF toggle persisted on the router; default ON at install, OFF is enforced at RPC and modem-worker entrance
- Existing VeCI admin login and existing WRITE ACL; no repeated approval, token, or separate SMS authentication
- One foreground Open Inbox button lists up to 16 stored SMS and displays sender/text; no background SMS reads
- Clear screen hides SMS; OFF immediately clears UI; no SMS stored in browser storage or logs
- Uses already tested CMGL PDU listing on /dev/ttyUSB2; cannot operate when OFF
- Old private ucode and worker are removed by the migration installer; metadata endpoint still present
- Real device release requires a one-command installer and feedback from physical MiFi UAT
