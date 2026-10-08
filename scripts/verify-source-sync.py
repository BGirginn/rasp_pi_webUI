#!/usr/bin/env python3
"""Compare every tracked source file and executable bit with a deployed Pi."""

import argparse
import hashlib
import json
import shlex
import subprocess
from pathlib import Path

REMOTE_CHECK = """
import hashlib, json, pathlib, sys
root = pathlib.Path(sys.argv[1]).resolve()
result = {}
for name in json.load(sys.stdin):
    path = (root / name).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        result[name] = None
    else:
        result[name] = [hashlib.sha256(path.read_bytes()).hexdigest(), bool(path.stat().st_mode & 0o100)]
print(json.dumps(result))
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", help="SSH user@host")
    parser.add_argument("--remote-root", default="/opt/pi-control/current")
    parser.add_argument("--control-path", help="Existing OpenSSH control socket")
    args = parser.parse_args()
    if args.target.startswith("-"):
        parser.error("SSH target cannot start with a dash")
    root = Path(__file__).resolve().parent.parent
    tracked = (
        subprocess.run(
            ["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True
        )
        .stdout.decode()
        .split("\0")
    )
    files = sorted(set(filter(None, tracked)))
    local = {
        name: [
            hashlib.sha256((root / name).read_bytes()).hexdigest(),
            bool((root / name).stat().st_mode & 0o100),
        ]
        for name in files
    }
    command = ["ssh", "-o", "ConnectTimeout=10"]
    if args.control_path:
        command.extend(["-S", args.control_path])
    command.extend(
        [
            args.target,
            f"python3 -c {shlex.quote(REMOTE_CHECK)} {shlex.quote(args.remote_root)}",
        ]
    )
    response = subprocess.run(
        command,
        input=json.dumps(files),
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    if response.returncode:
        print("SSH source verification failed:", response.stderr.strip())
        return 1
    remote = json.loads(response.stdout)
    differences = [name for name in files if local[name] != remote.get(name)]
    if differences:
        print("Source differences:")
        for name in differences:
            print(name)
        return 1
    print(f"Matched {len(files)} tracked files: SHA-256 contents and executable bits.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
