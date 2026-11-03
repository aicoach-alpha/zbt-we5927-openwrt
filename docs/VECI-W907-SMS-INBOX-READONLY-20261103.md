# W907-EC SMS inbox: receive-only release candidate

The 2026-11-03 live 25.12.5 firmware exposes SMS capability probes but not
veci.sms, and /veci/sms-center.css responds HTTP 404. Physical tests confirmed
AT+CMGF=?, AT+CPMS=?, AT+CNMI=?, AT+CUSD=? as supported.

This candidate pins Core 5af5bf5a6afbc16afdf5e1658614045cdd1580e2 and
adds the veci.sms read-only backend to veci-cellular-we5927 r2.

The new backend supports getConfig, setEnabled and listMessages only.
Enabled is opt-in, off by default, and persists in /etc/config/veci_sms.
Inbox uses AT+CMGF=0 then AT+CMGL=4 over the known W907 USB function 1.4
under a shared nonblocking /var/lock/we5927-at.lock. A malformed, oversized,
duplicate or unsolicited response returns an error rather than content.
The PDU parser does not log raw message contents. Browser gets at most 16
explicitly fetched PDUs, with no automatic reading, forwarding or storage.

Sending, deleting, drafts and Sent History remain disabled and are absent
from RPC method lists and ACL. A modem responding to capability tests is not
proof of working SMS transactions. Physical UAT must verify Inbox against
real messages before declaring support; do not display OTPs in audit logs.
Never restart the modem or network interfaces as part of an SMS patch.
Deploy file overlay first; require rollback and preserved Internet/SSH.
