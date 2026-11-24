#!/usr/bin/env python3
"""Disposable UCI option test double for original VeCI SSH/HTTPS host UAT.

Supports the exact UCI reads/writes involved; NOT a replacement for OpenWrt UCI.
Never reads/writes the host's /etc/config. The caller supplies -c and -t.
"""
import json
import os
from pathlib import Path
import shlex
import sys


def fail(message="missing"):
    print(message, file=sys.stderr)
    raise SystemExit(1)


def options(argv):
    directory = None
    delta = None
    words = []
    i = 0
    while i < len(argv):
        if argv[i] in ("-c", "-t"):
            if i + 1 >= len(argv):
                fail("missing directory")
            if argv[i] == "-c":
                directory = Path(argv[i+1])
            else:
                delta = Path(argv[i+1])
            i += 2
        elif argv[i] == "-q":
            i += 1
        else:
            words = argv[i:]
            break
    if directory is None or delta is None or not directory.is_dir():
        fail("explicit sandbox configuration and delta required")
    return directory, delta, words


def parse_file(path):
    lines = path.read_text().splitlines()
    sections = []
    current = None
    for index, line in enumerate(lines):
        try:
            parts = shlex.split(line,comments=True)
        except ValueError:
            fail("broken config")
        if not parts:
            continue
        if parts[0] == "config" and len(parts) >= 2:
            current = {"type": parts[1], "name":parts[2] if len(parts)>2 else None,
                       "start":index, "opts":{}}
            sections.append(current)
        elif parts[0] in ("option","list") and len(parts) >= 3 and current is not None:
            current["opts"].setdefault(parts[1],[]).append(parts[2])
    return lines,sections


def section_for(sections,selector):
    if selector.startswith("@"):
        if "[" not in selector or not selector.endswith("]"):
            fail()
        kind,n = selector[1:-1].split("[")
        try:index=int(n)
        except ValueError:fail()
        matching=[s for s in sections if s["type"]==kind]
        if 0 <= index < len(matching):
            return matching[index]
        fail()
    for section in sections:
        if section["name"]==selector:
            return section
    fail()


def apply_assignment(path, key, value):
    pieces=key.split(".",2)
    if len(pieces)!=3 or pieces[0]!=path.name:
        fail("bad staged key")
    lines,sections=parse_file(path)
    entry=section_for(sections,pieces[1])
    end=next((s["start"] for s in sections if s["start"]>entry["start"]),len(lines))
    for j in range(entry["start"]+1,end):
        tokens=shlex.split(lines[j],comments=True)
        if len(tokens)>=2 and tokens[0]=="option" and tokens[1]==pieces[2]:
            lines[j]=" option "+pieces[2]+" '"+value+"'"
            path.write_text("\n".join(lines)+"\n")
            return
    lines.insert(end," option "+pieces[2]+" '"+value+"'")
    path.write_text("\n".join(lines)+"\n")


def main():
    directory,delta,args=options(sys.argv[1:])
    if not args:
        fail("no operation")
    cmd=args[0]
    if cmd in ("get","set","commit","revert","changes") and len(args)<2:
        fail()
    if cmd == "get":
        key=args[1]
        pieces=key.split(".",2)
        if len(pieces) not in (2,3):
            fail()
        pkg,selector=pieces[:2]
        path=directory/pkg
        if not path.is_file():fail()
        lines,sections=parse_file(path)
        section=section_for(sections,selector)
        if len(pieces)==2:
            print(section["type"])
        else:
            values=section["opts"].get(pieces[2])
            if not values:fail()
            print(" ".join(values))
    elif cmd == "changes":
        p=delta/(args[1]+".json")
        if p.exists():
            for key,value in json.loads(p.read_text()).items():
                print(key+"='"+value+"'")
    elif cmd == "set":
        expr=args[1]
        if "=" not in expr:fail()
        key,value=expr.split("=",1)
        pkg=key.split(".",1)[0]
        if pkg not in ("dropbear","uhttpd"):fail("unsupported")
        # Validate section syntax before accepting changes.
        if len(key.split(".",2))!=3:fail()
        if not (directory/pkg).is_file():fail()
        _,sections=parse_file(directory/pkg)
        section_for(sections,key.split(".",2)[1])
        delta.mkdir(parents=True,exist_ok=True)
        p=delta/(pkg+".json")
        records=json.loads(p.read_text()) if p.exists() else {}
        records[key]=value
        p.write_text(json.dumps(records))
    elif cmd == "commit":
        pkg=args[1]
        if pkg not in ("dropbear","uhttpd"):fail()
        p=delta/(pkg+".json")
        if not p.exists():fail("no staged config")
        actions=json.loads(p.read_text())
        for key,value in actions.items():
            apply_assignment(directory/pkg,key,value)
        p.unlink()
    elif cmd == "revert":
        (delta/(args[1]+".json")).unlink(missing_ok=True)
    else:
        fail("unsupported uci operation: "+cmd)


if __name__=="__main__":
    main()
