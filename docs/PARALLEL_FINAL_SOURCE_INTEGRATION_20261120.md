Four isolated source branches integrated without firmware build or router writes.
- LTE d5caff6: RNDIS USB-device/driver/carrier provenance from VeCI a5af228; preserve older LTE route behavior after negative regression.
- Security 3ab2f7b: scoped login and logout from VeCI 31a72de; imported the original Node browser fixture tests.
- System b69b78a: GPIO37 kernel-owned watchdog read-only source from VeCI 461870a plus a scoped read-only status endpoint; no /dev/watchdog writes.
- Radio 0778d5c: read-only guest config/isolation inspector based on the existing source/veci-app-guest UCI contracts. No guest activation.
Independent source tests and integration are not evidence of functioning hardware or network isolation.
Original fixed 27 module denominator preserved; source partial and source verified remain distinct.
NO firmware build until the all-40 release gate independently verifies real code and tests.
