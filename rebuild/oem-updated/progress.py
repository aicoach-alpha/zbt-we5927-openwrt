"""Report current evidence levels; never infer functional PASS from fixtures."""
import collections
import json
from pathlib import Path
from prebuild_gate import check, check_candidate

a=json.loads(Path(__file__).with_name("operation-acceptance.json").read_text())
m={"reference_sha256":a["reference_sha256"],"operations":list(a["operations"])}
counts, release, release_gates=check(m,a)
_, candidate, candidate_gates=check_candidate(m,a)
print(json.dumps({
    "operation_states":dict(counts),
    "total":len(a["operations"]),
    "fixture_pass":counts["FIXTURE_PASS"],
    "functional_pass":counts["FUNCTIONAL_PASS"],
    "disabled_release_pass":counts["REVIEWED_DISABLED_PASS"],
    "unimplemented":counts["UNIMPLEMENTED"],
    "candidate_blocked_operations":len(candidate),
    "candidate_blocked_gates":candidate_gates,
    "release_blocked_operations":len(release),
    "release_blocked_gates":release_gates,
},indent=2))
