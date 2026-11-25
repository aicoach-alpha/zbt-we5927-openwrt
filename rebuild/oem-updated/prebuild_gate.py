"""Fail closed before expensive compilation; inventory comes from verified OEM staging."""
import argparse
import collections
import json
from pathlib import Path

REQUIRED_GATES = {"lte_policy_parity", "full_ui_integration", "security_regression",
                  "native_service_integration", "release_signing_preflight"}

def check(manifest, acceptance):
    if manifest.get("reference_sha256") != acceptance.get("reference_sha256"):
        raise ValueError("OEM reference mismatch")
    actual = set(manifest["operations"])
    entries = acceptance["operations"]
    if len(actual) != 158 or set(entries) != actual:
        raise ValueError("operation inventory mismatch")
    counts = collections.Counter(row["state"] for row in entries.values())
    blocked = []
    for op, row in entries.items():
        state = row["state"]
        # Denying an unsafe/nonexistent hardware feature must be reviewed and
        # its UI disabled and negative behavior tested, not silently counted.
        if state not in {"FUNCTIONAL_PASS", "REVIEWED_DISABLED_PASS"} or not row.get("evidence"):
            blocked.append(op)
    gates = acceptance["additional_gates"]
    if set(gates) != REQUIRED_GATES:
        raise ValueError("additional acceptance gate inventory mismatch")
    missing = sorted(k for k, v in gates.items() if v is not True)
    return counts, blocked, missing

def main():
    p = argparse.ArgumentParser()
    p.add_argument("manifest", type=Path)
    p.add_argument("acceptance", type=Path)
    a = p.parse_args()
    counts, blocked, missing = check(json.loads(a.manifest.read_text()), json.loads(a.acceptance.read_text()))
    print(json.dumps({"operation_states":counts,"blocked_operations":blocked,
                      "blocked_gates":missing},indent=2))
    if blocked or missing:
        raise SystemExit("PREBUILD_BLOCKED: complete and verify functionality before compiling")
    print("PREBUILD_ACCEPTANCE=PASS")

if __name__ == "__main__":
    main()
