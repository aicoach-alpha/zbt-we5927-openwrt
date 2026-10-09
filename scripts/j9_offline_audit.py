#!/usr/bin/env python3
"""J9 offline artifact gate. Never contacts or modifies any router."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath

IMAGE = 'openwrt-ramips-mt76x8-zbtlink_zbt-we5927-squashfs-sysupgrade.bin'
MANIFEST = 'openwrt-ramips-mt76x8-zbtlink_zbt-we5927.manifest'
APPS = ('guest', 'sqm', 'ddns', 'wireguard', 'voucher')
CORE = {'veci', 'veci-default-ui', 'veci-cellular-we5927', 'veci-update-we5927',
        'veci-app-catalog-we5927', 'we5927-lte'}
DEPENDENCIES = {'uspot', 'uspot-www', 'sqm-scripts', 'luci-app-sqm',
                'ddns-scripts', 'luci-app-ddns', 'wireguard-tools',
                'luci-proto-wireguard', 'kmod-wireguard', 'kmod-sched-cake'}
INDEXES = (
    'targets/ramips/mt76x8/packages/packages.adb',
    'packages/mipsel_24kc/base/packages.adb',
    'packages/mipsel_24kc/luci/packages.adb',
    'packages/mipsel_24kc/packages/packages.adb',
)
SHA_RE = re.compile(r'^([0-9a-fA-F]{64})\s+\*?(.+)$')
PIN_RE = re.compile(r'^(OpenWrt|packages|luci|routing|telephony|video):\s+([0-9a-f]{40})$', re.M)

class GateError(Exception):
    pass

class Artifact:
    def __init__(self, path):
        self.path = Path(path).resolve()
        if not self.path.exists():
            raise GateError('Missing artifact location')
        self.archive = zipfile.ZipFile(self.path) if self.path.is_file() else None
        if self.archive:
            records = self.archive.infolist()
            if len(records) > 2000 or sum(x.file_size for x in records) > 256*1024*1024:
                raise GateError('ZIP safety limit exceeded')
            files = [x.filename for x in records if not x.is_dir()]
            if len(files) != len(set(files)):
                raise GateError('Duplicate ZIP entries')
            for x in records:
                p = PurePosixPath(x.filename)
                if p.is_absolute() or '..' in p.parts or '\\' in x.filename:
                    raise GateError('Unsafe ZIP path')
                if stat.S_IFMT(x.external_attr >> 16) == stat.S_IFLNK:
                    raise GateError('Symlink ZIP entry forbidden')
            self.files = set(files)
        elif self.path.is_dir():
            self.files = set()
            for p in self.path.rglob('*'):
                if p.is_symlink():
                    raise GateError('Artifact symlinks forbidden')
                if p.is_file():
                    self.files.add(p.relative_to(self.path).as_posix())
            if len(self.files) > 2000:
                raise GateError('Too many artifact files')
        else:
            raise GateError('Invalid artifact path')

    def read(self, rel):
        if rel not in self.files:
            raise GateError('Missing file: '+rel)
        return self.archive.read(rel) if self.archive else (self.path / rel).read_bytes()

    def length(self, rel):
        if rel not in self.files:
            raise GateError('Missing file: '+rel)
        return self.archive.getinfo(rel).file_size if self.archive else (self.path / rel).stat().st_size

def checksums(raw):
    found = {}
    for line in raw.decode().splitlines():
        if not line.strip():
            continue
        m = SHA_RE.fullmatch(line.strip())
        if not m:
            raise GateError('Malformed SHA256 list')
        sha, name = m.groups()
        if '/' in name or '\\' in name or name in found or name.startswith('.'):
            raise GateError('Unsafe or duplicate SHA256 entry')
        found[name] = sha.lower()
    return found

def audit(firmware, feed, run_id):
    if not re.fullmatch(r'[0-9]{6,15}', str(run_id)):
        raise GateError('Invalid J8c run ID')
    reference = checksums(firmware.read('J8C-SHA256SUMS.txt'))
    expected = {IMAGE, MANIFEST, 'J8C-INVENTORY.txt', 'target-sha256sums'}
    if set(reference) != expected:
        raise GateError('Incomplete or unexpected firmware SHA256 inventory')
    for p, digest in reference.items():
        if hashlib.sha256(firmware.read(p)).hexdigest() != digest:
            raise GateError('SHA256 failure: '+p)
    target = checksums(firmware.read('target-sha256sums'))
    if any(target.get(p) != reference[p] for p in (IMAGE, MANIFEST)):
        raise GateError('OpenWrt target SHA256 mismatch')
    size = firmware.length(IMAGE)
    if not 0 < size <= 7808*1024:
        raise GateError('Firmware exceeds WE5927 image budget')
    manifest = {}
    for line in firmware.read(MANIFEST).decode().splitlines():
        if not line.strip():
            continue
        if ' - ' not in line:
            raise GateError('Invalid package manifest')
        name, version = line.split(' - ',1)
        if not name or not version or name in manifest:
            raise GateError('Invalid package manifest entry')
        manifest[name] = version
    missing = CORE - manifest.keys()
    if missing:
        raise GateError('Firmware core missing: '+','.join(sorted(missing)))
    if any('veci-app-'+a in manifest for a in APPS):
        raise GateError('Optional apps unexpectedly installed in base image')
    kernel = manifest.get('kernel','').split('~')[0]
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+',kernel):
        raise GateError('Kernel missing')
    for n,v in manifest.items():
        if n.startswith('kmod-') and not (v.startswith(kernel+'-') or v.startswith(kernel+'.')):
            raise GateError('Core kernel ABI mismatch: '+n)

    for index in INDEXES:
        if feed.length(index) < 100:
            raise GateError('Missing or empty APK index: '+index)
    apks = sorted(p for p in feed.files if p.endswith('.apk'))
    if len(apks)<25:
        raise GateError('Feed truncated')
    required = DEPENDENCIES | {'veci-app-'+a for a in APPS}
    located = {}
    for rel in apks:
        base = PurePosixPath(rel).name
        if base.startswith('veci-app-') and not re.fullmatch(r'veci-app-[a-z0-9-]+-1-r[0-9]+\.apk',base):
            raise GateError('Unexpected VeCI APK name')
        for pkg in required:
            if re.fullmatch(re.escape(pkg)+r'-[0-9][^/]*\.apk', base):
                if pkg in located:
                    raise GateError('Duplicate package: '+pkg)
                located[pkg] = rel
    if required - located.keys():
        raise GateError('App/dependency APK missing: '+','.join(sorted(required-located.keys())))
    for pkg in ('kmod-wireguard','kmod-sched-cake'):
        if not PurePosixPath(located[pkg]).name.startswith(pkg+'-'+kernel+'-'):
            raise GateError('Kernel module ABI mismatch: '+pkg)
        if not located[pkg].startswith('targets/ramips/mt76x8/packages/'):
            raise GateError('Kernel package in wrong feed: '+pkg)
    inventory = firmware.read('J8C-INVENTORY.txt').decode()
    pins = dict(PIN_RE.findall(inventory))
    if set(pins) != {'OpenWrt','packages','luci','routing','telephony','video'}:
        raise GateError('Pinned source revisions absent')
    selected = {}
    inside = False
    for row in inventory.splitlines():
        if row == 'Selected app APKs:':
            inside = True
            continue
        if row == 'Matched kernel packages:':
            inside = False
        if not inside or not row.strip():
            continue
        m = re.fullmatch(r'([0-9]+) bin/(.+\.apk)',row.strip())
        if not m:
            raise GateError('Malformed APK inventory')
        n, rel = m.groups()
        if rel in selected or feed.length(rel) != int(n):
            raise GateError('APK inventory size/uniqueness mismatch: '+rel)
        selected[rel] = int(n)
    for app in APPS:
        if not any(PurePosixPath(p).name.startswith('veci-app-'+app+'-') for p in selected):
            raise GateError('VeCI App absent in inventory: '+app)
    return {
        'j9':'OFFLINE_PASS', 'release_decision':'NO_GO', 'run_id':str(run_id),
        'firmware':{'sha256':reference[IMAGE],'bytes':size,'kernel':kernel,'installed_packages':len(manifest)},
        'feed':{'apk_count':len(apks),'indexes':list(INDEXES),'apps':list(APPS),'inventory_selected':len(selected)},
        'source_pins':pins,
        'gates':{'checksum':'PASS','feed_presence':'PASS','kernel_version':'PASS',
                 'apk_signatures':'NOT_TESTED','dependency_solver':'NOT_TESTED',
                 'live_router_uat':'NOT_TESTED','sysupgrade_T':'NOT_TESTED',
                 'release':'BLOCKED'},
        'notes':['Both artifacts must originate from same GitHub Actions run; file content alone cannot independently attest origin.',
                 'This audit does not verify cryptographic APK signatures, solve dependencies, or perform device I/O.',
                 'Never flash or install the matched APK feed on the old kernel without explicit approval and full UAT.']
    }

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--firmware',required=True)
    p.add_argument('--feed',required=True)
    p.add_argument('--run-id',required=True)
    p.add_argument('--report',default='j9-readiness.json')
    args=p.parse_args(argv)
    try:
        result=audit(Artifact(args.firmware),Artifact(args.feed),args.run_id)
    except (GateError, OSError, UnicodeError, ValueError, zipfile.BadZipFile) as e:
        result={'j9':'OFFLINE_FAIL','release_decision':'NO_GO','error':str(e)}
    Path(args.report).write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps(result,sort_keys=True,indent=2))
    return 0 if result['j9']=='OFFLINE_PASS' else 1

if __name__ == '__main__':
    sys.exit(main())
