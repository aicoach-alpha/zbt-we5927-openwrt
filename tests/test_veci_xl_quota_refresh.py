#!/usr/bin/env python3
"""Focused no-network tests for the real root-owned XL cache refresh shell."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

SRC=Path("source/veci-telco-indonesia/files/usr/libexec/veci-xl-quota-refresh").read_text()
MOCK_JSON='''#!/usr/bin/env python3
import json,sys
args=sys.argv
x=json.load(open(args[args.index("-i")+1]))
for key in args[args.index("-e")+1][2:].split("."):
    x=x[key]
print(str(x).lower() if isinstance(x,bool) else x)
'''
def case(name,parsed,epoch_offset=0,expect=True):
    with tempfile.TemporaryDirectory(prefix="veci-xl-refresh-") as temp:
        p=Path(temp); private=p/"private"; private.mkdir(mode=0o700)
        cache=p/"cache"; mock=p/"mocks";mock.mkdir()
        for field,value in {
            "id_token":"aaa.bbb.ccc","access_token":"access_sample_long",
            "refresh_token":"refresh_sample_long",
            "verified_number":"6281234567890","verified_epoch":str(int(time.time())-epoch_offset),
            "xdata_key":"z"*32,"signature_secret":"s"*32,"api_key":"key_value",
        }.items():
            item=private/field
            item.write_text(value+"\n" if field not in ("xdata_key",) else value)
            item.chmod(0o600)
        crypto=mock/"veci-xl-crypto"
        crypto.write_text('''#!/bin/sh
if [ "$1" = xdata ]; then printf 'QUJDREVGR0g=\\n'; exit 0; fi
if [ "$1" = signature ]; then printf 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\\n'; exit 0; fi
exit 3
''')
        chain=mock/"veci-xl-quota-chain"
        chain.write_text("#!/bin/sh\nprintf '%s\\n' '"+json.dumps(parsed,separators=(",",":"))+"'\n")
        for tool in ("veci-xl-quota-http","veci-xl-quota-normalize"):
            (mock/tool).write_text("#!/bin/sh\nexit 0\n")
        for path in mock.iterdir():path.chmod(0o755)
        jf=mock/"jsonfilter";jf.write_text(MOCK_JSON);jf.chmod(0o755)
        script=(SRC.replace("ROOT=/tmp/veci-telco-private",f"ROOT={private}")
                  .replace("CACHE=/tmp/veci-telco",f"CACHE={cache}")
                  .replace("LOCK=/tmp/veci-xl-quota-refresh.lock",f"LOCK={p/'lock'}")
                  .replace("PATH=/usr/sbin:/usr/bin:/sbin:/bin",
                           f"PATH={mock}:/usr/sbin:/usr/bin:/sbin:/bin")
                  .replace("/usr/libexec/",str(mock)+"/")
                  .replace("/usr/bin/jsonfilter",str(jf)))
        app=p/"run";app.write_text(script)
        subprocess.run(["sh","-n",str(app)],check=True)
        run=subprocess.run(["sh",str(app),"--refresh"],capture_output=True,text=True)
        assert run.returncode==(0 if expect else 1),(name,run.returncode,run.stdout,run.stderr)
        assert "access_sample_long" not in run.stdout+run.stderr
        target=cache/"quota-xl.json"
        if expect:
            assert "VECI_XL_QUOTA_REFRESH=pass" in run.stdout
            d=json.loads(target.read_text())
            assert d["state"]=="ready" and d["source"]=="carrier_authenticated"
            assert d["remaining_bytes"]==123 and d["total_bytes"]==1000
            assert (target.stat().st_mode & 0o777)==0o600
        else:
            assert not target.exists()
            assert "VECI_XL_QUOTA_REFRESH=blocked" in run.stdout
        for f in ("signature","signature_time","body.json"):
            assert not (private/f).exists()
        print("VECI_XL_QUOTA_CACHE_CASE=pass",name)

if __name__=="__main__":
    if os.geteuid()!=0:raise SystemExit("root-only test")
    good=dict(ok=True,parsed_only=True,provider="xl",remaining_bytes=123,total_bytes=1000)
    case("trusted",good,expect=True)
    case("wrong_provider",dict(good,provider="other"),expect=False)
    case("remaining_greater",dict(good,remaining_bytes=1001),expect=False)
    case("no_parsed_only",dict(good,parsed_only=False),expect=False)
    case("expired_verified_session",good,epoch_offset=1900,expect=False)
    assert "AT+CMGS" not in SRC and "AT+CUSD" not in SRC
    print("VECI_XL_QUOTA_CACHE_FOCUSED=pass")
