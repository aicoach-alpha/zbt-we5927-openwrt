#!/usr/bin/env python3
"""Host-side BITS-XL quota JSON normalizer; NOT a modem or router API client.
Input: JSON from a separately authenticated myXL client running on a server.
Output: minimal schema to be imported via veci-quota-import on a TEST router.
No purchase/payment/OTP handling. Never writes credentials or subscriber number.
"""
import argparse
from datetime import datetime, timezone
import json
import sys

MAX=10000000000000
def expiry_epoch(value):
    if isinstance(value,bool) or value is None:return 0
    if isinstance(value,(int,float)):
        n=int(value)
        return n//1000 if n>100000000000 else n
    if isinstance(value,str):
        if value.isdigit():return expiry_epoch(int(value))
        try:
            parsed=datetime.fromisoformat(value.replace("Z","+00:00"))
            if parsed.tzinfo is None:
                parsed=parsed.replace(tzinfo=timezone.utc)
            return int(parsed.timestamp())
        except ValueError:
            return 0
    return 0

def normalize(raw):
    if not isinstance(raw,dict):raise ValueError("invalid_api_response")
    if raw.get("ok") is False:raise ValueError("upstream_quota_unavailable")
    payload=raw.get("quota",raw)
    if isinstance(payload,dict) and isinstance(payload.get("data"),dict):
        payload=payload["data"]
    if not isinstance(payload,dict) or not isinstance(payload.get("quotas"),list):
        raise ValueError("quota_packages_missing")
    total=0
    remaining=0
    expiries=[]
    for item in payload["quotas"]:
        if not isinstance(item,dict):continue
        expiry=expiry_epoch(item.get("end_date") or item.get("expired_at") or item.get("expiry"))
        counted=False
        for b in item.get("benefits",[]):
            if not isinstance(b,dict) or str(b.get("data_type","")).upper()!="DATA":
                continue
            if b.get("is_unlimited"):
                continue  # Unlimited quota cannot be represented by finite bytes.
            a,c=b.get("total"),b.get("remaining")
            if isinstance(a,bool) or isinstance(c,bool) or not isinstance(a,(int,float)) or not isinstance(c,(int,float)):
                continue
            if not float(a).is_integer() or not float(c).is_integer():
                continue
            a,c=int(a),int(c)
            if not (0<=c<=a<=MAX):raise ValueError("invalid_quota_values")
            total+=a
            remaining+=c
            counted=True
        if counted and expiry>0:expiries.append(expiry)
    if total<=0 or total>MAX:raise ValueError("finite_data_quota_missing")
    if not expiries:raise ValueError("expiry_missing")
    # Earliest package expiry is conservative; user can see package detail
    # only when provider supports it, rather than a misleading latest date.
    return {"operator":"xl","total_bytes":total,"remaining_bytes":remaining,
            "expires_at":min(expiries)}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",default="-")
    args=ap.parse_args()
    with (sys.stdin if args.input=="-" else open(args.input,encoding="utf-8")) as f:
        text=f.read(200000)
    try:out=normalize(json.loads(text))
    except (ValueError,TypeError) as exc:
        # Never log upstream JSON; may contain personal information.
        print("quota_normalization_failed: "+str(exc),file=sys.stderr)
        return 2
    print(json.dumps(out,separators=(",",":")))
    return 0
if __name__=="__main__":sys.exit(main())
