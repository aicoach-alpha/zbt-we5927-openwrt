#!/usr/bin/env python3
"""Regenerate *actual* source test receipts for every active owner VeCI module.

Staging is separate from the repo. No source-verification claims are written
unless every scoped test ran successfully, every test method was observed as
"ok", and all expected files exist. No hardware/UAT PASS is recorded.
"""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
M=ROOT/"rebuild/veci-v2/contracts/owner-final-source-evidence.json"
C=ROOT/"rebuild/veci-v2/contracts/veci-v2-rebuild-contract.json"
G=ROOT/"rebuild/veci-v2/ci/source-completion-gate.py"
ROOT_STAGE=Path("/tmp/veci-integration39-source-acceptance-20261124")

def fail(message): raise RuntimeError(message)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def module_methods(record):
    tests=[]
    for method in record.get("test_ids",[]):
        hits=[]
        for f in record.get("test_source_files",[]):
            if not f.endswith(".py"):continue
            file=ROOT/f
            if not file.is_file():fail("missing test source "+f)
            tree=ast.parse(file.read_text(),filename=f)
            for node in tree.body:
                if not isinstance(node,ast.ClassDef):continue
                for fn in node.body:
                    if isinstance(fn,(ast.FunctionDef,ast.AsyncFunctionDef)) and fn.name==method:
                        hits.append(file.stem+"."+node.name+"."+fn.name)
        if not hits:fail("missing scoped test method "+method)
        tests+=hits
    if not tests:fail("empty test list")
    return list(dict.fromkeys(tests))

def check_manifest(entries):
    contract=json.loads(C.read_text())
    ids=[x["id"] for x in contract["required_core"]]
    if len(ids)!=39 or len(set(ids))!=39 or "lte_ussd" in ids:fail("active modules not exact 39")
    if set(entries)!=set(ids):fail("evidence module set mismatch")
    for id in ids:
        r=entries[id]
        if not r.get("implementation_files") or not r.get("test_source_files") or not r.get("test_ids"):
            fail("incomplete manifest "+id)
        for f in r["implementation_files"]+r["test_source_files"]:
            path=ROOT/f
            if not path.is_file() or path.is_symlink() or not path.stat().st_size or not path.resolve().is_relative_to(ROOT):
                fail("missing/unsafe source "+id+" "+f)

def run():
    e=json.loads(M.read_text())
    records=e["modules"]
    check_manifest(records)
    ROOT_STAGE.mkdir(parents=True,exist_ok=True)
    logs=ROOT_STAGE/"logs"
    logs.mkdir(exist_ok=True)
    env=dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"]="1"
    env["PYTHONPATH"]=str(ROOT/"scripts/tests")+":"+str(ROOT/"tests")+":"+env.get("PYTHONPATH","")
    summary={}
    for id in sorted(records):
        record=records[id]
        tests=module_methods(record)
        command=[sys.executable,"-m","unittest","-v",*tests]
        try:
            proc=subprocess.run(command,cwd=ROOT,text=True,capture_output=True,timeout=105,env=env)
            log=proc.stderr.replace("\r\n","\n").replace("\r","\n")
            (logs/(id+".txt")).write_text(log)
            (logs/(id+".stdout.txt")).write_text(proc.stdout)
            passed=set(re.findall(r"^(test_\w+) \([^\n]+\) \.\.\. ok$",log,re.M))
            ok=(proc.returncode==0 and set(record["test_ids"]) <= passed
                and re.search(r"^Ran [1-9]\d* tests? in [\d.]+s$",log,re.M)
                and log.rstrip().endswith("\nOK"))
            summary[id]={"status":"PASS" if ok else "FAIL","exit":proc.returncode,
                         "required_ids":record["test_ids"],"passed_ids":sorted(passed),
                         "tests_run":len(tests),
                         "log_sha256":sha(logs/(id+".txt")),
                         "log_path":str(logs/(id+".txt"))}
            print(f"{id}: {'PASS' if ok else 'FAIL'} ({len(passed)}/{len(record['test_ids'])} required test names) exit={proc.returncode}",flush=True)
        except subprocess.TimeoutExpired:
            summary[id]={"status":"TIMEOUT","exit":124,"required_ids":record["test_ids"]}
            print(f"{id}: TIMEOUT",flush=True)
    report=ROOT_STAGE/"summary.json"
    report.write_text(json.dumps(summary,indent=2,ensure_ascii=False)+"\n")
    passed=sum(x["status"]=="PASS" for x in summary.values())
    print(f"REAL_SCOPE_TESTS_PASS={passed}/39",flush=True)
    return 0 if passed==39 else 3

def apply():
    report=ROOT_STAGE/"summary.json"
    if not report.is_file():fail("missing actual staged run")
    summary=json.loads(report.read_text())
    entries=json.loads(M.read_text())["modules"]
    check_manifest(entries)
    if set(summary)!=set(entries):fail("wrong staged set")
    if any(x["status"]!="PASS" for x in summary.values()):fail("some actual tests failed")
    import datetime
    utc=datetime.datetime.now(datetime.timezone.utc).isoformat()
    for id,record in entries.items():
        stage=ROOT_STAGE/"logs"/(id+".txt")
        if not stage.is_file() or sha(stage)!=summary[id]["log_sha256"]:
            fail("tampered/missing test output "+id)
        observed=set(re.findall(r"^(test_\w+) \([^\n]+\) \.\.\. ok$",stage.read_text(),re.M))
        if not set(record["test_ids"])<=observed or not stage.read_text().rstrip().endswith("\nOK"):
            fail("not actually PASS "+id)
        files=record["implementation_files"]+record["test_source_files"]
        record["source_sha256"]={f:sha(ROOT/f) for f in files}
        record["status"]="pass"
        record["scope"]="source_verified_no_hardware_uat"
        logrel="docs/source-acceptance/"+id+".txt"
        record["receipt"]={
            "kind":"executed_source_tests","exit_code":0,"hardware_uat":"not_run",
            "log_file":logrel,"log_sha256":sha(stage),"executed_utc":utc
        }
    # Ensure current source stays same: do not write any output until the
    # complete manifest & logs are checked. Once written verify via source gate.
    for id in sorted(entries):
        src=ROOT_STAGE/"logs"/(id+".txt")
        dst=ROOT/"docs/source-acceptance"/(id+".txt")
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(src,dst)
    M.write_text(json.dumps({"modules":dict(sorted(entries.items()))},ensure_ascii=False,indent=2)+"\n")
    # Use exact gate the release workflow executes; refuse nonzero.
    gate=subprocess.run([sys.executable,str(G)],cwd=ROOT,text=True,capture_output=True)
    (ROOT_STAGE/"gate-after-refresh.json").write_text(gate.stdout)
    if gate.returncode:
        fail("source gate still blocked: "+gate.stdout[:1500])
    print("SOURCE_GATE_VERIFIED_39_OF_39=PASS",flush=True)
    return 0

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("command",choices=["run","apply"])
    args=parser.parse_args()
    try:sys.exit(run() if args.command=="run" else apply())
    except Exception as e:
        print("SOURCE_ACCEPTANCE_FAIL_CLOSED:",e,file=sys.stderr)
        sys.exit(3)
