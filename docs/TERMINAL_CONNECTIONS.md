# Terminal connection lifecycle

The **Connect** button opens a restricted WebSocket session directly. **Full Shell**
still requires the existing break-glass authentication flow. A rejected login or
elevation does not trigger automatic reconnection.

Only the current socket may update the terminal. Replacing or closing it cancels
pending retries and disposes its xterm input subscription. Unexpected transport
closures retry restricted mode at 1, 2 and 4 seconds, then stop with an error.
Disconnect also cancels a connection attempt or a pending retry. Full shell
sessions require an explicit new connection after closing.

Application-level JSON heartbeat messages are not sent to the PTY: the backend
treats text messages as shell input. WebSocket protocol keepalive remains the
transport's responsibility.

## Regression checks

```sh
cd panel/ui
npm test -- src/pages/Terminal.test.jsx
npm run lint
npm test
npm run build
```

The tests cover the old full-to-restricted reconnect race, rejected credentials,
bounded retries, replacing input handlers, full-shell input without heartbeat
injection, empty command output, and disconnect/unmount cleanup.

## Pi hotfix on 2026-11-05

The deployed base is `b763edeb7198c1b711c6537aad6e0ec2887eaa06`, under
`/opt/pi-control/releases/telemetry-charts-20261008-b763ede`.
Only `Terminal.jsx` and its rebuilt UI were updated. The deployment build used
the Pi's matching base source and lockfile, with 66 UI tests passing. The current
local tree, which also contains the pending integration removal, passed 61 UI
tests. Other pending source changes were not part of this hotfix.

`SOURCE_COMMIT` retains the base commit. `terminal-ui-hotfix.json` in that release
records the applied source/index hashes and backup path. The original source and
UI are preserved at `/opt/pi-control/backups/terminal-ui-20261105-1042`.
New hashed assets were uploaded first and `index.html` replaced atomically last;
old assets remain available to existing browser sessions. No service restart or
database migration was needed.

To restore the previous terminal UI on that Pi:

```sh
cd /opt/pi-control/releases/telemetry-charts-20261008-b763ede/panel/ui
cp -p /opt/pi-control/backups/terminal-ui-20261105-1042/Terminal.jsx src/pages/Terminal.jsx
cp -p /opt/pi-control/backups/terminal-ui-20261105-1042/dist/index.html dist/.index-rollback.html
mv dist/.index-rollback.html dist/index.html
```

Live verification uses the Caddy WebSocket endpoint over Tailscale: full mode
without elevation must be rejected, restricted `whoami` must succeed, and `uptime`
must succeed on the same connection after 35 seconds. Diagnostic authentication
uses a short-lived token held only in process memory; passwords and stored
credentials are not changed. Browser rendering and an elevated interactive PTY
were not directly exercised in this session.
