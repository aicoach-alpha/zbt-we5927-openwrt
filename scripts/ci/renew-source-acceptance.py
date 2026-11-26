#!/usr/bin/env python3
"""Execute exact scoped source tests and capture receipts for 39 VeCI modules.

Requires native UCI/libubox environment in CI. Fail closed on failures/skips.
Never edits the checked-in evidence; outputs a reviewable manifest/log folder.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import inspect
import io
import json
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT/"rebuild/veci-v2/contracts/veci-v2-rebuild-contract.json"
EVIDENCE = ROOT/"rebuild/veci-v2/contracts/owner-final-source-evidence.json"
CANONICAL = ROOT/"rebuild/veci-v2/ci/source-completion-gate.py"

def all_tests(suite):
    for case in suite:
        if isinstance(case, unittest.TestSuite):
            yield from all_tests(case)
        else:
            yield case

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--only", nargs="*", default=[])
    args=parser.parse_args()
    output=args.output.expanduser().resolve()
    if output == ROOT or ROOT in output.parents:
        # A CI workspace path is okay only under dedicated test-evidence.
        if not output.is_relative_to(ROOT/"test-evidence"):
            raise SystemExit("Output must be outside source tree or under test-evidence")
    if output.exists():
        raise SystemExit("Refuse to overwrite existing source receipts")
    data=json.loads(EVIDENCE.read_text())
    modules={x["id"]:x for x in json.loads(CONTRACT.read_text())["required_core"]}
    if set(data["modules"])!=set(modules) or len(modules)!=39:
        raise SystemExit("Exact 39 active module evidence required")
    target=args.only or sorted(modules)
    if not set(target).issubset(modules):
        raise SystemExit("Unknown module selection")
    loader=unittest.TestLoader()
    suite=loader.discover(str(ROOT/"scripts/tests"),pattern="test_*.py")
    # All receipt-scoped methods are in scripts/tests. The standalone tests/
    # folder has no Python package and is already checked by full-suite CI.
    allcases=list(all_tests(suite))
    by_method=defaultdict(list)
    for case in allcases:
        name=getattr(case,"_testMethodName","")
        source=Path(inspect.getfile(type(case))).resolve()
        if name.startswith("test_"):
            by_method[name].append((source,case))
    # Every method reference must have exactly one implementation in approved test files.
    planned=[]
    for key in target:
        original=data["modules"][key]
        selections=[]
        allowed={str((ROOT/f).resolve()) for f in original["test_source_files"]}
        for name in original["test_ids"]:
            matched=[case for source,case in by_method[name] if str(source) in allowed]
            if len(matched)!=1:
                raise SystemExit(f"AMBIGUOUS_OR_MISSING_SCOPED_TEST:{key}:{name}:{len(matched)}")
            selections.append(matched[0])
        planned.append((key,original,selections))
    output.mkdir(parents=True)
    logs=output/"logs"
    logs.mkdir()
    accepted={}
    failures=[]
    for index,(name,original,selections) in enumerate(planned,1):
        tests=unittest.TestSuite([type(x)(x._testMethodName) for x in selections])
        stream=io.StringIO()
        runner=unittest.TextTestRunner(stream=stream,verbosity=2,failfast=True)
        # Actual stdout from tests may contain sensitive test data; don't print
        # it into CLI logs. Tests themselves are isolated to simulated fixtures.
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result=runner.run(tests)
        log=stream.getvalue()
        if (not result.wasSuccessful() or result.skipped or
            result.testsRun!=len(selections) or
            not log.rstrip().endswith("OK")):
            failures.append(dict(module=name,run=result.testsRun,failures=len(result.failures),
                                 errors=len(result.errors),skipped=len(result.skipped)))
            (logs/(name+".failed.txt")).write_text(log)
            print(f"MODULE_SOURCE_TEST_FAILED:{name} failures={len(result.failures)} errors={len(result.errors)} skipped={len(result.skipped)}",file=sys.stderr)
            continue
        log_file=logs/(name+".txt")
        log_file.write_text(log)
        item=json.loads(json.dumps(original))
        item["source_sha256"]={}
        for rel in item["implementation_files"]+item["test_source_files"]:
            path=(ROOT/rel).resolve()
            if not path.is_relative_to(ROOT) or not path.is_file() or path.is_symlink():
                raise SystemExit("BAD_SOURCE_PATH:"+str(rel))
            item["source_sha256"][rel]=hashlib.sha256(path.read_bytes()).hexdigest()
        item["receipt"]={"kind":"executed_source_tests","exit_code":0,
                         "hardware_uat":"not_run","log_file":"docs/source-acceptance/"+name+".txt",
                         "log_sha256":hashlib.sha256(log_file.read_bytes()).hexdigest()}
        accepted[name]=item
        print(f"MODULE_SOURCE_TEST_PASS:{index}/{len(planned)}:{name}:{result.testsRun}",flush=True)
    (output/"test-run-summary.json").write_text(json.dumps({
        "source_commit_requires_exact_git_checkout":True,
        "total_modules":len(planned),"accepted_modules":len(accepted),
        "failed_modules":failures,
        "test_count":sum(len(x[2]) for x in planned)},indent=2)+"\n")
    if failures or len(accepted)!=len(planned):
        raise SystemExit("NO_RECEIPTS_ACCEPTED_WITH_UNTESTED_MODULES")
    if len(target)==39:
        (output/"owner-final-source-evidence.json").write_text(json.dumps(
            {"modules":accepted},indent=2)+"\n")
    return 0

if __name__=="__main__":
    sys.exit(main())
