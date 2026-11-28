#!/usr/bin/env python3
"""Exact-source defect register and release-blocker audit for WE5927 VeCI v2.

No firmware build, no router changes, no synthetic PASSes. Accepted test
references must be real source files; CI must still actually RUN their tests.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
C=ROOT/"rebuild/veci-v2/contracts"
REGISTRY=C/"veci-v2-bug-registry-20261126.json"
CONTRACT=C/"veci-v2-rebuild-contract.json"
EVIDENCE=C/"owner-final-source-evidence.json"
ALLOWED={"source_fixed","source_open","requires_hardware_verification",
         "requires_ci_verification","mitigation_only"}
PHYSICAL={"not_tested","pass_new_candidate"}

def audit():
    errors=[]
    try:
        registry=json.loads(REGISTRY.read_text())
        contract=json.loads(CONTRACT.read_text())
        evidence=json.loads(EVIDENCE.read_text())
    except (OSError,ValueError) as exc:
        return {"ok":False,"errors":["unreadable_registry_or_contract:"+type(exc).__name__]}
    modules={x["id"] for x in contract["required_core"]}
    if len(modules)!=39 or "lte_ussd" in modules:
        errors.append("module_inventory_not_exact_39_without_ussd")
    if registry.get("board")!="zbtlink,zbt-we5927":
        errors.append("invalid_board")
    bugs=registry.get("bugs")
    if not isinstance(bugs,list) or not bugs:
        errors.append("empty_bug_register")
        bugs=[]
    found=set()
    coverage=set()
    count={"source_fixed":0,"source_open":0,"requires_hardware_verification":0,
           "requires_ci_verification":0,"mitigation_only":0}
    for bug in bugs:
        if not isinstance(bug,dict):
            errors.append("invalid_bug_entry")
            continue
        name=bug.get("id")
        if not isinstance(name,str) or not name or name in found:
            errors.append("duplicate_or_invalid_bug_id")
            continue
        found.add(name)
        state=bug.get("source_state")
        if state not in ALLOWED:
            errors.append("invalid_state:"+name)
            continue
        count[state]+=1
        if bug.get("candidate_hardware") not in PHYSICAL:
            errors.append("invalid_hardware_state:"+name)
        for value in ("summary","root_cause","protection","area","severity"):
            if not isinstance(bug.get(value),str) or not bug[value].strip():
                errors.append("missing_"+value+":"+name)
        claimed=bug.get("affected_modules")
        if not isinstance(claimed,list) or not claimed or not set(claimed).issubset(modules):
            errors.append("invalid_affected_modules:"+name)
        else:
            coverage.update(claimed)
        references=bug.get("regression_test_files")
        if not isinstance(references,list) or not references:
            errors.append("missing_test_refs:"+name)
        else:
            for rel in references:
                if (not isinstance(rel,str) or "/" in rel or "\\" in rel or
                    not rel.startswith("test_") or not rel.endswith(".py")):
                    errors.append("bad_test_ref:"+name)
                    continue
                path=ROOT/"scripts/tests"/rel
                if not path.is_file() or path.is_symlink() or "def test_" not in path.read_text():
                    errors.append("test_ref_not_executable:"+name+":"+rel)
    if coverage!=modules:
        errors.append("modules_not_audited:"+",".join(sorted(modules-coverage)))
    hashes={}
    for name,record in evidence.get("modules",{}).items():
        mismatch=[]
        for rel,expected in record.get("source_sha256",{}).items():
            src=ROOT/rel
            if not src.is_file() or src.is_symlink() or hashlib.sha256(src.read_bytes()).hexdigest()!=expected:
                mismatch.append(rel)
        if mismatch:
            hashes[name]=mismatch
    missing_hardware=[x["id"] for x in contract["required_core"] if x["physical_uat"]!="pass"]
    pending_test=[x["id"] for x in bugs if x.get("candidate_hardware")!="pass_new_candidate"]
    high_open=[x["id"] for x in bugs if x.get("source_state")=="source_open"]
    summary={
        "ok":not errors,"board":registry.get("board"),
        "registered_known_cases":len(bugs),"source_states":count,
        "covered_active_modules":len(coverage),"required_active_modules":len(modules),
        "historical_receipt_hash_mismatches":len(hashes),
        "modules_requiring_hardware_uat":len(missing_hardware),
        "bug_cases_not_accepted_on_new_candidate":len(pending_test),
        "known_source_open":high_open,
        "source_build_permitted":not(errors or high_open or hashes),
        "release_permitted":not(errors or high_open or hashes or missing_hardware or pending_test),
        "errors":errors,
    }
    return summary

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--gate",choices=["register","source","release"],default="register")
    args=parser.parse_args()
    report=audit()
    print(json.dumps(report,indent=2))
    if report.get("errors"):
        return 3
    if args.gate=="source" and not report["source_build_permitted"]:
        return 3
    if args.gate=="release" and not report["release_permitted"]:
        return 3
    return 0

if __name__=="__main__":
    sys.exit(main())
