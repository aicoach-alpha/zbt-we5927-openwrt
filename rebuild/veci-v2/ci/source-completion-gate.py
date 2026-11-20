#!/usr/bin/env python3
"""Fail closed BEFORE any OpenWrt compilation until 40 core modules have evidence.

Hardware UAT comes later; source completion is a distinct prerequisite.
This script does not produce binaries, change router config or sign artifacts.
"""
from pathlib import Path
import json
import sys

BASE = Path(__file__).resolve().parents[1]
CONTRACT = BASE / "contracts/veci-v2-rebuild-contract.json"
EVIDENCE = BASE / "contracts/owner-final-source-evidence.json"


def audit(contract: dict, evidence: dict) -> list[str]:
    issues = []
    required = contract.get("required_core", [])
    if len(required) != 40 or len({x["id"] for x in required}) != 40:
        issues.append("required_core_wrong_count_or_duplicates")
    index = evidence.get("modules", {})
    if set(index) != {x["id"] for x in required}:
        issues.append("source_evidence_missing_or_extra_modules")
    root = BASE.parents[1]
    test_sources = list((root / "scripts/tests").glob("test_*.py")) + list((root / "tests").glob("test_*.py"))
    known_tests = {}
    for candidate in test_sources:
        text = candidate.read_text()
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("def test_"):
                func = line.split("def ", 1)[1].split("(", 1)[0]
                known_tests.setdefault(func, []).append(candidate)
    for item in required:
        name = item["id"]
        if item["v2_state"] != "source_verified":
            issues.append("not_source_verified:" + name)
        record = index.get(name, {})
        if record.get("status") != "pass" or not record.get("implementation_files") or not record.get("test_ids"):
            issues.append("missing_implementation_or_test_evidence:" + name)
            continue
        for rel in record["implementation_files"]:
            path = BASE.parents[1] / rel
            if not path.is_file() or not path.stat().st_size:
                issues.append("missing_implementation_file:" + name)
                break
        for test_id in record["test_ids"]:
            if not isinstance(test_id, str) or test_id not in known_tests:
                issues.append("invalid_test_reference:" + name)
    return sorted(set(issues))


def main():
    contract = json.loads(CONTRACT.read_text())
    evidence = json.loads(EVIDENCE.read_text()) if EVIDENCE.is_file() else {}
    issues = audit(contract, evidence)
    print(json.dumps({
        "gate": "PRE_COMPILE_OWNER_FINAL_SOURCE",
        "build_permitted": not issues,
        "core_total": len(contract.get("required_core", [])),
        "source_verified": sum(x.get("v2_state") == "source_verified" for x in contract.get("required_core", [])),
        "blockers_count": len(issues),
        "blockers": issues,
    }, indent=2))
    return 0 if not issues else 3

if __name__ == "__main__":
    sys.exit(main())
