# One source tree for local development, GitHub and the Pi

The active Pi source tree is `/opt/pi-control/current`, a symlink to a release.
The synchronized baseline includes the Pi's newer UI, security fixes, operations
features and single-writer agent telemetry. The earlier local history remains in
Git and was backed up before synchronization. The two previously unrelated Git
histories were merged, so updating GitHub does not require force-pushing.

The old local installer options `--profile`, `--web-port` and `--with-adguard` are
not supported by this baseline. Use `./install.sh --help` and
`./deploy-native.sh --help` for its actual options. Existing Pi configuration and
AdGuard installation are preserved; source synchronization does not reinstall them.

Portable development and mocked tests on macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
cd panel/ui
npm ci
npm run check:modules
npm run lint
npm test
npm run build
cd ../api
../../.venv/bin/python -m pytest --basetemp=/tmp/pi-control-api-tests
cd ../../agent
../.venv/bin/python -m pytest
```

Use a dedicated `/tmp` test directory on macOS; its default temporary directory
is under the protected `/var` tree. Build the UI before API tests: SPA routing and its security tests require `dist`.
The portable test dependencies omit native Linux D-Bus/GObject; hardware operations
still require the Pi environment and `agent/requirements.txt`. Core API versions
match the tested Pi versions, and the UI dependencies use `package-lock.json`.

After changing source, commit and push it, deploy that exact commit as a fresh
release, then verify all tracked file contents and executable bits:

```sh
python3 scripts/verify-source-sync.py fou4@100.116.120.20
```

The expected result is `Matched ... tracked files`. The Pi release's
`SOURCE_COMMIT` file records its Git commit. Keep the previous release until the
new API health check and source comparison pass. Rollback changes `current` to
the previous release and restarts `pi-agent` and `pi-control`; it does not restore
or overwrite databases.

Runtime databases, secrets, `.env` files, virtual environments, caches and build
outputs are intentionally outside the Git source comparison. SQLite WAL/SHM
sidecars and personal `.claude` settings are not source and must not be published.
