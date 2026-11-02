# Recover WE5927 incremental build safely

The 2026-11-02 cached build failed inside radcli 1.3.0 install-exec-hook.
It creates TWO compatibility symlinks with plain ln -s:
libfreeradius-client.so and libradiusclient-ng.so. These links remain
in the disposable ipkg-install/usr/lib staging directory after a
successful run and a repeated make world tries to create them again.

The official bounded VeCI container launcher now uses a preflight that
validates both links before any build is started. It removes only links
pointing exactly to libradcli.so, refuses unexpected files or targets,
checks the external cache root, current tested source build ID, and
ensures no active builder exists.

Upstream will recreate both links during package installation. This
does NOT remove the actual library, erase the cache, modify router
networking, or alter source packages. The helper is idempotent and
returns a hard failure for unexpected filesystem state.

It is a development-cache repair, not authorization for firmware flashing.
