#!/usr/bin/env python3
"""Fail closed BEFORE any OpenWrt compilation until all 39 active core modules have evidence.

Hardware UAT comes later; source completion is a distinct prerequisite.
This script does not produce binaries, change router config or sign artifacts.
"""
from pathlib import Path
import hashlib
import json
import re
import sys

BASE = Path(__file__).resolve().parents[1]
CONTRACT = BASE / "contracts/veci-v2-rebuild-contract.json"
EVIDENCE = BASE / "contracts/owner-final-source-evidence.json"

# Owner permanently retired USSD. 39 (not historical 40) is the only
# accepted source inventory; a future feature addition requires owner approval.
ACTIVE_CORE_COUNT = 39
RETIRED_CORE = {"lte_ussd"}


def receipt_passed(log, methods):
    """Accept only successful unittest runs that actually report each method."""
    text = log.read_text(errors="replace")
    passed = set(re.findall(r"^(test_\w+) \([^\n]+\) \.\.\. ok$", text, re.M))
    return (bool(methods) and set(methods).issubset(passed)
            and re.search(r"^Ran [1-9]\d* tests? in [\d.]+s$", text, re.M)
            and text.rstrip().endswith("\nOK")
            and not re.search(r"^FAILED(?: |$)", text, re.M))


def audit(contract: dict, evidence: dict) -> list[str]:
    issues = []
    required = contract.get("required_core", [])
    ids = [x["id"] for x in required]
    if len(required) != ACTIVE_CORE_COUNT or len(set(ids)) != ACTIVE_CORE_COUNT:
        issues.append("required_core_wrong_count_or_duplicates")
    if RETIRED_CORE.intersection(ids):
        issues.append("retired_module_reintroduced")
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
            path = (root / rel).resolve() if isinstance(rel,str) else root
            if not isinstance(rel,str) or not path.is_relative_to(root) or not path.is_file() or not path.stat().st_size:
                issues.append("missing_or_unsafe_implementation_file:" + name)
                break
        for test_id in record["test_ids"]:
            if not isinstance(test_id, str) or test_id not in known_tests:
                issues.append("invalid_test_reference:" + name)
        # Evidence for verified modules must be reproducible and tied to the
        # exact version of the source/test inputs. A module is NOT accepted
        # by placing a generic test name and a package file in the manifest.
        if item["v2_state"] == "source_verified":
            files = record.get("source_sha256")
            test_files = record.get("test_source_files")
            receipt = record.get("receipt")
            if (not isinstance(files,dict) or not isinstance(test_files,list)
                    or not test_files or not isinstance(receipt,dict)):
                issues.append("missing_scoped_source_acceptance:" + name)
                continue
            refs = record["implementation_files"] + test_files
            if set(files) != set(refs):
                issues.append("source_hash_manifest_mismatch:" + name)
                continue
            for rel in refs:
                path = (root / rel).resolve() if isinstance(rel,str) else root
                if (not isinstance(rel,str) or not path.is_relative_to(root) or not path.is_file()
                        or hashlib.sha256(path.read_bytes()).hexdigest() != files.get(rel)):
                    issues.append("source_hash_mismatch:" + name)
                    break
            resolved_tests = [path for method in record["test_ids"]
                              for path in known_tests.get(method,[])]
            if not resolved_tests or not all(path.resolve().relative_to(root).as_posix() in test_files
                                             for path in resolved_tests):
                issues.append("test_not_scoped_to_module:" + name)
            log_rel = receipt.get("log_file")
            log = (root / log_rel).resolve() if isinstance(log_rel,str) else root
            if (receipt.get("kind") != "executed_source_tests" or
                    receipt.get("exit_code") != 0 or
                    receipt.get("hardware_uat") != "not_run" or
                    not isinstance(log_rel,str) or not log.is_relative_to(root) or not log.is_file() or
                    hashlib.sha256(log.read_bytes()).hexdigest() != receipt.get("log_sha256") or
                    not receipt_passed(log, record["test_ids"])):
                issues.append("invalid_source_test_receipt:" + name)
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
