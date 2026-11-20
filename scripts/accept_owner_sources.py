"""Re-run declared unittest suites and bind owner evidence to their inputs."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "rebuild/veci-v2/contracts"


def digest(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def main():
    specs = json.loads((CONTRACTS / "owner-acceptance-scopes.json").read_text())
    contract_path = CONTRACTS / "veci-v2-rebuild-contract.json"
    evidence_path = CONTRACTS / "owner-final-source-evidence.json"
    contract = json.loads(contract_path.read_text())
    evidence = json.loads(evidence_path.read_text())
    modules = {module["id"]: module for module in contract["required_core"]}
    cache = {}
    records = {}
    for name in sys.argv[1:]:
        scope = specs[name]
        assert modules[name]["physical_uat"] == "not_run"
        output = []
        for suite in scope["suites"]:
            if suite not in cache:
                cmd = [sys.executable, "-m", "unittest", "discover", "-s", "scripts/tests",
                       "-p", suite, "-v"]
                env = {**os.environ, "PYTHONOPTIMIZE": "", "PYTHONDONTWRITEBYTECODE": "1"}
                result = subprocess.run(cmd, cwd=ROOT, env=env, text=True,
                                        capture_output=True, timeout=180)
                if result.returncode or not re.search(r"^OK$", result.stderr, re.M):
                    raise SystemExit(result.stdout + result.stderr)
                cache[suite] = result.stdout + "\n" + result.stderr
            output.append(cache[suite])
        log = "\n".join(output)
        passed = set(re.findall(r"^(test_\w+) \([^\n]+\) \.\.\. ok$", log, re.M))
        if not set(scope["test_ids"]).issubset(passed):
            raise SystemExit(f"Unexecuted acceptance method for {name}: {log}")
        rel = f"docs/source-acceptance/{name}.txt"
        (ROOT / rel).write_text(log)
        files = scope["implementation_files"] + scope["test_source_files"]
        records[name] = {k: scope[k] for k in ("implementation_files","test_source_files","test_ids")}
        records[name].update(status="pass", scope="source_verified_no_hardware_uat",
                             source_sha256={f:digest(f) for f in files},
                             receipt=dict(kind="executed_source_tests",exit_code=0,
                                          hardware_uat="not_run",log_file=rel,log_sha256=digest(rel)))
    for name, record in records.items():
        evidence["modules"][name] = record
        modules[name]["v2_state"] = "source_verified"
    write_json(contract_path, contract)
    write_json(evidence_path, evidence)
    print("Verified source:", ", ".join(records))


if __name__ == "__main__":
    main()
