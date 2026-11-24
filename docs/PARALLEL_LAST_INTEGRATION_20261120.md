Three independently tested source-only worktrees, no image build:
- monitor 15a47bd: existing we5927-lte ping_interval with UCI stale guard and no modem restart, reused VeCI 077d88d.
- addons f030ab1: source reuse 1984f18 via separate scoped veci.v2.addon endpoint; do not modify byte-identical legacy startup services.
- update 925fcff: source reuse e868223 fail-closed firmware install policy with verify_only default; apply and stable-apply guarded and browser honors install_allowed receipt.
All source revisions are partial pending native runtime and owner-router physical UAT.
Source integration does not authorize sysupgrade or build.
