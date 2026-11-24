#!/usr/bin/env python3
"""Re-execute scoped source acceptance for previously verified but drifted modules.

Does not promote incomplete modules. Verifies complete source/test scope from
the owner manifest and executed methods, then re-hashes actual tested files.
Never builds, signs, installs firmware, or calls the physical router.
"""
from pathlib import Path
import hashlib,json,os,subprocess,sys
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
CONTRACT=ROOT/"rebuild/veci-v2/contracts/veci-v2-rebuild-contract.json"
EVIDENCE=ROOT/"rebuild/veci-v2/contracts/owner-final-source-evidence.json"
SCOPES=ROOT/"rebuild/veci-v2/contracts/owner-acceptance-scopes.json"
MODULES=("ipv6_ra_dhcpv6","static_routes_policy","system_ipv6_guarded_settings_toggle")
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    contract=json.loads(CONTRACT.read_text())
    scope=json.loads(SCOPES.read_text())
    data=json.loads(EVIDENCE.read_text())
    index={r["id"]:r for r in contract["required_core"]}
    selected=tuple(sys.argv[1:]) if len(sys.argv)>1 else MODULES
    if not selected or len(set(selected))!=len(selected) or any(name not in MODULES for name in selected):
        raise ValueError("Only explicit already source-verified scopes are accepted")
    pending={}
    for name in selected:
        spec=scope[name]
        old=data["modules"].get(name)
        assert isinstance(old,dict) and old["status"]=="pass"
        assert index[name]["v2_state"]=="source_verified"
        assert index[name]["physical_uat"]=="not_run"
        for key in ("implementation_files","test_source_files","test_ids"):
            assert spec[key] == old[key],name+" source scope was altered"
        files=spec["implementation_files"]+spec["test_source_files"]
        assert all((ROOT/f).is_file() and (ROOT/f).stat().st_size for f in files)
        logs=[]
        for file in spec["suites"]:
            cmd=["python3","-m","unittest","discover",
                 "-s",str(ROOT/"scripts/tests"),"-p",file,"-v"]
            task=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,
                                timeout=90,env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1"})
            output=task.stdout+"\n"+task.stderr
            if task.returncode or "Ran " not in output or "\nOK\n" not in output:
                print("FAILED_SCOPED_TEST",name,file,output[-4500:],file=sys.stderr)
                raise SystemExit(5)
            logs.append("$ "+" ".join(cmd)+"\n"+output)
        logged="\n".join(logs)
        for method in spec["test_ids"]:
            if method not in logged:
                raise ValueError(name+": expected test not executed: "+method)
        log_file=ROOT/"docs/source-acceptance"/(name+".txt")
        pending[name]=(files,log_file,logged)
    # Only mutate evidence after every test in every scope passed.
    for name,(files,log_file,content) in pending.items():
        log_file.write_text(content)
        record=data["modules"][name]
        record["source_sha256"]={f:digest(ROOT/f) for f in files}
        record["receipt"]={
            "kind":"executed_source_tests",
            "exit_code":0,
            "hardware_uat":"not_run",
            "log_file":log_file.relative_to(ROOT).as_posix(),
            "log_sha256":digest(log_file),
            "executed_utc":datetime.now(timezone.utc).isoformat(timespec="seconds")
        }
        print("REFRESHED_AND_REEXECUTED",name,"hashes",len(files),
              "log_sha256",digest(log_file))
    EVIDENCE.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n")
if __name__=="__main__":
    main()
