#!/bin/bash
# Upload a file or directory to a Raspberry Pi over SSH/SCP.

set -euo pipefail

PI_TARGET="${PI_TARGET:-}"
REMOTE_DIR="${REMOTE_DIR:-~}"
SCP_PORT="${SCP_PORT:-}"
LOCAL_PATH=""

print_usage() {
    cat <<'EOF'
Usage: ./upload_to_pi.sh [OPTIONS] <local_path> [user@host] [remote_directory]

Options:
  --target USER@HOST   SSH target. Can also be set with PI_TARGET.
  --remote-dir DIR     Remote destination directory (default: ~)
  --port PORT          SSH/SCP port. Can also be set with SCP_PORT.
  -h, --help           Show this help text

Environment:
  PI_TARGET             Default SSH target, for example pi@192.168.1.50
  PI_USER/PI_HOST       Legacy target pair used when PI_TARGET is not set
  REMOTE_DIR            Default remote destination directory
  SCP_PORT              Default SSH/SCP port

Examples:
  ./upload_to_pi.sh ./image.png pi@192.168.1.50 ~/Downloads
  ./upload_to_pi.sh --target pi@192.168.1.50 --remote-dir /tmp ./dist
  PI_TARGET=pi@192.168.1.50 ./upload_to_pi.sh ./archive.tar.gz
EOF
}

fail() {
    echo "ERR $1" >&2
    exit 1
}

set_port() {
    local port="$1"

    if [[ ! "$port" =~ ^[0-9]+$ ]] || [[ "$port" -lt 1 ]] || [[ "$port" -gt 65535 ]]; then
        fail "Invalid port: $port"
    fi

    SCP_PORT="$port"
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --target)
                [[ $# -ge 2 ]] || fail "--target requires USER@HOST"
                PI_TARGET="$2"
                shift
                ;;
            --target=*)
                PI_TARGET="${1#*=}"
                ;;
            --remote-dir)
                [[ $# -ge 2 ]] || fail "--remote-dir requires a directory"
                REMOTE_DIR="$2"
                shift
                ;;
            --remote-dir=*)
                REMOTE_DIR="${1#*=}"
                ;;
            --port)
                [[ $# -ge 2 ]] || fail "--port requires a value"
                set_port "$2"
                shift
                ;;
            --port=*)
                set_port "${1#*=}"
                ;;
            -h|--help)
                print_usage
                exit 0
                ;;
            -*)
                fail "Unknown option: $1"
                ;;
            *)
                if [[ -z "$LOCAL_PATH" ]]; then
                    LOCAL_PATH="$1"
                elif [[ -z "$PI_TARGET" ]]; then
                    PI_TARGET="$1"
                elif [[ "$REMOTE_DIR" == "~" ]]; then
                    REMOTE_DIR="$1"
                else
                    fail "Unexpected argument: $1"
                fi
                ;;
        esac
        shift
    done
}

resolve_legacy_target() {
    if [[ -z "$PI_TARGET" && -n "${PI_USER:-}" && -n "${PI_HOST:-}" ]]; then
        PI_TARGET="${PI_USER}@${PI_HOST}"
    fi
}

ensure_remote_dir() {
    local quoted_remote_dir=""
    local ssh_args=()

    [[ "$REMOTE_DIR" != "~" && "$REMOTE_DIR" != "~/" ]] || return

    if [[ -n "$SCP_PORT" ]]; then
        ssh_args=(-p "$SCP_PORT")
    fi

    printf -v quoted_remote_dir '%q' "$REMOTE_DIR"
    ssh "${ssh_args[@]}" "$PI_TARGET" "mkdir -p $quoted_remote_dir"
}

upload_path() {
    local remote_path="$REMOTE_DIR"
    local scp_args=()

    if [[ -n "$SCP_PORT" ]]; then
        scp_args=(-P "$SCP_PORT")
    fi

    if [[ -d "$LOCAL_PATH" ]]; then
        scp_args+=(-r)
    fi

    if [[ "$remote_path" == "~" ]]; then
        remote_path="~/"
    else
        remote_path="${remote_path%/}/"
    fi

    echo "Uploading '$LOCAL_PATH' to '$PI_TARGET:$remote_path'..."
    scp "${scp_args[@]}" "$LOCAL_PATH" "$PI_TARGET:$remote_path"
    echo "OK Upload complete."
}

main() {
    resolve_legacy_target
    parse_args "$@"
    resolve_legacy_target

    [[ -n "$LOCAL_PATH" ]] || {
        print_usage
        exit 1
    }
    [[ -e "$LOCAL_PATH" ]] || fail "Local path not found: $LOCAL_PATH"
    [[ -n "$PI_TARGET" ]] || fail "Missing target. Use user@host or --target USER@HOST."

    ensure_remote_dir
    upload_path
}

main "$@"
