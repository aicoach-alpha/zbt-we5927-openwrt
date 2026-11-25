# Owner VeCI — parallel source acceptance, 23 November 2026

NO firmware build. NO physical router operations. Final image prohibited until all 40 core source gates pass.

Isolated code tracks based on owner HEAD 04e8058:
- auth 2f3879c, staged e2a25f0: actual browser login/logout VM, HTTPS-only login, SID validation, session teardown, scoped RPC and read-only baseline ACL.
- access e5e2b35, staged eb54cfa: actual SSH/HTTPS RPC provider in BusyBox ash with isolated UCI shim, staged idle timeout, TLS certificate guard, stale revisions, session locking and pending configuration.
- provenance f0c7619, staged 8691453: enforce immutable original Git blob hashes and auditable subsequent commits; refuse undocumented working tree changes.
- login/access test logs, code/tests and receipt SHA-256 independently generated through module-specific acceptance.
- static_routes_policy: original scoped native test re-executed PASS before refreshing stale source hashes and log receipt.
- IPv6 RA and guarded IPv6 toggle receipts were NOT refreshed: native UCI test was skipped on current host; skipped tests cannot constitute acceptance.

Staging full main unittest: 385 tests OK, 5 skipped; additional: 38 OK. No skipped test used to issue new receipts.
Staging progress: 7/27 source verified (+3 vs main 4/27); 20 partial; 0 without source. 10/40 core marked source_verified; build gate still BLOCKED with 63 blockers, build_permitted=false.
No hardware UAT, user router untouched. Main branch retains dirty ongoing edits, this work stayed isolated until safe integration.
