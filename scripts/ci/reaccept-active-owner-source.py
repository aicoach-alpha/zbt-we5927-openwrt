#!/usr/bin/env python3
"""Re-run each explicitly scoped native source test before refreshing current hashes.
Never fabricate receipt success or touch the router. Requires native test env.
"""
from __future__ import annotations
import argparse
import ast
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
MANIFEST=ROOT/"rebuild/veci-v2/contracts/owner-final-source-evidence.json"
CONTRACT=ROOT/"rebuild/veci-v2/contracts/veci-v2-rebuild-contract.json"

def registry():
    known=defaultdict(list)
    for folder in ("scripts/tests","tests"):
        for p in (ROOT/folder).glob("test_*.py"):
            try:
                tree=ast.parse(p.read_text())
            except SyntaxError:
                continue
            for cls in tree.body:
                if isinstance(cls,ast.ClassDef):
                    for method in cls.body:
                        if isinstance(method,(ast.FunctionDef,ast.AsyncFunctionDef)) and method.name.startswith("test_"):
                            known[method.name].append((p.relative_to(ROOT).as_posix(),cls.name))
    return known

def scoped_calls(name,record,known):
    calls=[]
    for method in record["test_ids"]:
        matches=[(p,c) for p,c in known[method] if p in record["test_source_files"]]
        if len(matches)!=1:
            raise ValueError(f"{name}: not exactly one scoped test for {method}")
        p,c=matches[0]
        calls.append(f"{Path(p).stem}.{c}.{method}")
    return calls

def run_scope(name, record, known, timeout):
    calls=scoped_calls(name,record,known)
    env=os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"]="1"
    env["PYTHONPATH"]=os.pathsep.join([str(ROOT/"scripts/tests"),str(ROOT/"tests"),env.get("PYTHONPATH","")])
    try:
        r=subprocess.run([sys.executable,"-m","unittest","-v",*calls],cwd=ROOT,
                         env=env,text=True,capture_output=True,timeout=timeout)
        log=(r.stdout or "")+(r.stderr or "")
        exit_code=r.returncode
    except subprocess.TimeoutExpired:
        return name,False,"TIMEOUT",{},None
    methods=set(re.findall(r"^(test_\w+) \([^\n]+\) \.\.\. ok$",log,re.M))
    valid=(
        exit_code==0 and
        set(record["test_ids"]).issubset(methods) and
        bool(re.search(r"^Ran [1-9]\d* tests? in [\d.]+s$",log,re.M)) and
        log.rstrip().endswith("\nOK") and
        not re.search(r"^FAILED(?: |$)",log,re.M)
    )
    if not valid:
        return name,False,log[-1800:],{},None
    paths=record["implementation_files"]+record["test_source_files"]
    if len(set(paths))!=len(paths):
        return name,False,"duplicate source path",{},None
    hashes={}
    for rel in paths:
        path=(ROOT/rel).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file() or not path.stat().st_size:
            return name,False,f"missing or unsafe source: {rel}",{},None
        hashes[rel]=hashlib.sha256(path.read_bytes()).hexdigest()
    return name,True,log,hashes,len(calls)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--apply",action="store_true",help="update PASS receipts only after running all real tests")
    p.add_argument("--workers",type=int,default=3)
    p.add_argument("--timeout",type=int,default=130)
    args=p.parse_args()
    if not args.apply: print("REFUSED: explicitly specify --apply");return 3
    if not os.environ.get("VECI_LIBUBOX_PREFIX") or not os.environ.get("VECI_HOST_UCI"):
        print("REFUSED: source pinned native host tools env first");return 3
    evidence=json.loads(MANIFEST.read_text())
    contract=json.loads(CONTRACT.read_text())
    required={x["id"] for x in contract["required_core"]}
    if len(required)!=39 or required!=set(evidence["modules"]) or "lte_ussd" in required:
        print("REFUSED: 39 active non-USSD modules not consistent");return 3
    known=registry()
    outcomes={}
    with ThreadPoolExecutor(max_workers=max(1,min(args.workers,4))) as ex:
        futures={ex.submit(run_scope,name,evidence["modules"][name],known,args.timeout):name
                 for name in sorted(required)}
        for future in as_completed(futures):
            name,ok,log,hashes,n=future.result()
            outcomes[name]=(ok,log,hashes,n)
            print(f"{name}: {'SOURCE_TEST_PASS' if ok else 'SOURCE_TEST_FAIL'} {n or ''}",flush=True)
            if not ok: print(str(log)[-380:].replace("\n"," ")[:380],flush=True)
    passed=0
    for name in sorted(required):
        ok,log,hashes,n=outcomes[name]
        if not ok:continue
        rec=evidence["modules"][name]
        receipt_path=ROOT/"docs/source-acceptance"/f"{name}.txt"
        receipt_path.parent.mkdir(parents=True,exist_ok=True)
        # Only actual subprocess unittest stdout+stderr with named ok methods may be written.
        receipt_path.write_text(log)
        rec["source_sha256"]=hashes
        rec["receipt"]={
          "kind":"executed_source_tests",
          "exit_code":0,
          "hardware_uat":"not_run",
          "log_file":receipt_path.relative_to(ROOT).as_posix(),
          "log_sha256":hashlib.sha256(log.encode()).hexdigest()
        }
        rec["status"]="pass"
        passed+=1
    evidence["modules"]={k:evidence["modules"][k] for k in sorted(required)}
    MANIFEST.write_text(json.dumps(evidence,indent=2,ensure_ascii=False)+"\n")
    failed=[k for k in sorted(required) if not outcomes[k][0]]
    print(f"REACCEPT_RESULT={passed}/{len(required)} PASS, failures={len(failed)}")
    print("FAILED_MODULES="+",".join(failed))
    return 0 if not failed else 5

if __name__=="__main__": sys.exit(main())
