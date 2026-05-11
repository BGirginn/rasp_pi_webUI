#!/bin/bash
# Pi Control Panel - AdGuard Home installer/configurator

set -euo pipefail

readonly CONFIG_DIR="/etc/pi-control"
readonly SERVICE_ENV_FILE="$CONFIG_DIR/pi-control.env"
readonly ADGUARD_URL="http://127.0.0.1:3000/control"
readonly ADGUARD_BOOTSTRAP_URL="http://127.0.0.1:3001/control"
readonly ADGUARD_FILTER_URL="https://adguardteam.github.io/HostlistsRegistry/assets/filter_1.txt"
readonly CLOUDFLARE_SECURITY_DOH="https://security.cloudflare-dns.com/dns-query"

ADGUARD_ADMIN_USER="${ADGUARD_ADMIN_USER:-pi-control}"
ADGUARD_ADMIN_PASSWORD="${ADGUARD_ADMIN_PASSWORD:-}"

info() {
    echo "  -> $1"
}

warn() {
    echo "  WARN $1"
}

fail() {
    echo "  ERR $1" >&2
}

require_root() {
    if [[ $EUID -ne 0 ]]; then
        fail "Run this script with sudo."
        exit 1
    fi
}

load_env_file() {
    if [[ -f "$SERVICE_ENV_FILE" ]]; then
        set -a
        # shellcheck disable=SC1090
        source "$SERVICE_ENV_FILE"
        set +a
    fi
    ADGUARD_ADMIN_USER="${ADGUARD_ADMIN_USER:-pi-control}"
}

quote_env_value() {
    local value="$1"
    value="${value//\\/\\\\}"
    value="${value//\"/\\\"}"
    printf '"%s"' "$value"
}

set_env_var() {
    local key="$1"
    local value="$2"
    local tmp_file=""

    mkdir -p "$CONFIG_DIR"
    tmp_file="$(mktemp)"

    if [[ -f "$SERVICE_ENV_FILE" ]]; then
        grep -v "^${key}=" "$SERVICE_ENV_FILE" > "$tmp_file" || true
    fi

    printf '%s=%s\n' "$key" "$(quote_env_value "$value")" >> "$tmp_file"
    mv "$tmp_file" "$SERVICE_ENV_FILE"
    chmod 600 "$SERVICE_ENV_FILE"
}

ensure_credentials() {
    if [[ -z "$ADGUARD_ADMIN_PASSWORD" ]]; then
        ADGUARD_ADMIN_PASSWORD="$(openssl rand -base64 30 | tr -d '\n')"
        set_env_var "ADGUARD_ADMIN_PASSWORD" "$ADGUARD_ADMIN_PASSWORD"
    fi
    set_env_var "ADGUARD_ADMIN_USER" "$ADGUARD_ADMIN_USER"
}

port53_users() {
    if command -v ss >/dev/null 2>&1; then
        ss -H -tulnp 2>/dev/null | awk '$5 ~ /:53$/ {print}'
    elif command -v netstat >/dev/null 2>&1; then
        netstat -tulnp 2>/dev/null | awk '$4 ~ /:53$/ {print}'
    fi
}

check_port53_available() {
    local users=""
    users="$(port53_users || true)"

    if [[ -n "$users" ]] && [[ "$users" != *"AdGuardHome"* ]]; then
        fail "Port 53 is already in use:"
        echo "$users" >&2
        fail "Common conflicts: systemd-resolved, dnsmasq, pihole-FTL. Free port 53 before using --with-adguard."
        exit 1
    fi
}

is_adguard_installed() {
    [[ -x /opt/AdGuardHome/AdGuardHome ]] || command -v AdGuardHome >/dev/null 2>&1
}

install_adguard() {
    if is_adguard_installed; then
        info "AdGuard Home is already installed."
        return
    fi

    info "Installing AdGuard Home via the official stable installer."
    curl -s -S -L https://raw.githubusercontent.com/AdguardTeam/AdGuardHome/master/scripts/install.sh | sh -s -- -v
}

start_adguard() {
    systemctl enable AdGuardHome >/dev/null 2>&1 || true
    systemctl restart AdGuardHome

    for _ in {1..30}; do
        if is_configured || curl -fsS "$ADGUARD_URL/install/get_addresses" >/dev/null 2>&1; then
            return
        fi
        sleep 1
    done

    fail "AdGuard Home did not start on 127.0.0.1:3000."
    journalctl -u AdGuardHome -n 30 --no-pager >&2 || true
    exit 1
}

json_initial_config() {
    ADGUARD_ADMIN_USER="$ADGUARD_ADMIN_USER" ADGUARD_ADMIN_PASSWORD="$ADGUARD_ADMIN_PASSWORD" python3 - <<'PY'
import json
import os

print(json.dumps({
    "web": {"ip": "127.0.0.1", "port": 3001},
    "dns": {"ip": "0.0.0.0", "port": 53},
    "username": os.environ["ADGUARD_ADMIN_USER"],
    "password": os.environ["ADGUARD_ADMIN_PASSWORD"],
}))
PY
}

set_final_web_bind() {
    local config_file="/opt/AdGuardHome/AdGuardHome.yaml"

    if [[ ! -f "$config_file" ]]; then
        return
    fi

    python3 - <<'PY'
from pathlib import Path

path = Path("/opt/AdGuardHome/AdGuardHome.yaml")
lines = path.read_text().splitlines()
out = []
in_http = False
http_indent = None
for line in lines:
    stripped = line.strip()
    indent = len(line) - len(line.lstrip(" "))
    if stripped == "http:":
        in_http = True
        http_indent = indent
        out.append(line)
        continue
    if in_http and indent <= http_indent and stripped:
        in_http = False
    if in_http and stripped.startswith("address:"):
        out.append("  address: 127.0.0.1:3000")
    else:
        out.append(line)
path.write_text("\n".join(out) + "\n")
PY

    systemctl restart AdGuardHome
    for _ in {1..30}; do
        if is_configured; then
            return
        fi
        sleep 1
    done

    fail "AdGuard Home did not come back on 127.0.0.1:3000 after final bind update."
    exit 1
}

agh_get() {
    curl -fsS -u "$ADGUARD_ADMIN_USER:$ADGUARD_ADMIN_PASSWORD" "$ADGUARD_URL/$1"
}

agh_post() {
    local path="$1"
    local payload="$2"
    curl -fsS -u "$ADGUARD_ADMIN_USER:$ADGUARD_ADMIN_PASSWORD" \
        -H "Content-Type: application/json" \
        -X POST \
        --data "$payload" \
        "$ADGUARD_URL/$path" >/dev/null
}

is_configured() {
    local status_json=""
    status_json="$(agh_get status 2>/dev/null || true)"
    STATUS_JSON="$status_json" python3 - <<'PY'
import json
import os
import sys

try:
    data = json.loads(os.environ.get("STATUS_JSON", ""))
except json.JSONDecodeError:
    sys.exit(1)

sys.exit(0 if data.get("running") is not None and data.get("version") else 1)
PY
}

configure_initial() {
    if is_configured; then
        info "AdGuard Home API authentication works."
        return
    fi

    info "Applying initial AdGuard Home configuration."
    if curl -fsS \
        -H "Content-Type: application/json" \
        -X POST \
        --data "$(json_initial_config)" \
        "$ADGUARD_URL/install/configure" >/dev/null; then
        for _ in {1..20}; do
            if curl -fsS -u "$ADGUARD_ADMIN_USER:$ADGUARD_ADMIN_PASSWORD" "$ADGUARD_BOOTSTRAP_URL/status" >/dev/null 2>&1; then
                set_final_web_bind
                return
            fi
            sleep 1
        done
    fi

    fail "AdGuard Home is installed, but Pi Control cannot authenticate or complete first setup."
    fail "If this is an existing AdGuard Home install, set ADGUARD_ADMIN_USER and ADGUARD_ADMIN_PASSWORD in $SERVICE_ENV_FILE."
    exit 1
}

dns_config_payload() {
    ADGUARD_UPSTREAM_DOH="$CLOUDFLARE_SECURITY_DOH" python3 - <<'PY'
import json
import os

try:
    data = json.loads(os.environ.get("INPUT_JSON", "{}"))
except json.JSONDecodeError:
    data = {}

data.pop("default_local_ptr_upstreams", None)
data["upstream_dns"] = [os.environ["ADGUARD_UPSTREAM_DOH"]]
data["bootstrap_dns"] = ["1.1.1.1", "1.0.0.1"]
data["protection_enabled"] = True
data["blocking_mode"] = data.get("blocking_mode") or "default"
data["upstream_mode"] = data.get("upstream_mode") or "load_balance"
print(json.dumps(data))
PY
}

ensure_filter_url() {
    local status_json=""
    local exists="false"

    status_json="$(agh_get filtering/status || echo '{}')"
    exists="$(INPUT_JSON="$status_json" FILTER_URL="$ADGUARD_FILTER_URL" python3 - <<'PY'
import json
import os

try:
    data = json.loads(os.environ.get("INPUT_JSON", "{}"))
except json.JSONDecodeError:
    data = {}

url = os.environ["FILTER_URL"]
filters = data.get("filters") or []
print("true" if any(item.get("url") == url for item in filters) else "false")
PY
)"

    if [[ "$exists" == "true" ]]; then
        return
    fi

    agh_post "filtering/add_url" "$(python3 - <<'PY'
import json
print(json.dumps({
    "name": "AdGuard DNS filter",
    "url": "https://adguardteam.github.io/HostlistsRegistry/assets/filter_1.txt",
    "whitelist": False,
}))
PY
)"
    agh_post "filtering/refresh" '{"whitelist":false}' || true
}

configure_defaults() {
    local dns_info=""
    local dns_payload=""

    dns_info="$(agh_get dns_info || echo '{}')"
    dns_payload="$(INPUT_JSON="$dns_info" dns_config_payload)"
    agh_post "dns_config" "$dns_payload"
    agh_post "protection" '{"enabled":true}'
    agh_post "filtering/config" '{"enabled":true,"interval":24}'
    agh_post "safebrowsing/enable" '{}'
    agh_post "parental/disable" '{}'
    ensure_filter_url
}

install_flow() {
    require_root
    load_env_file
    check_port53_available
    ensure_credentials
    install_adguard
    start_adguard
    configure_initial
    configure_defaults
    systemctl restart pi-control >/dev/null 2>&1 || true
}

status_flow() {
    load_env_file
    if agh_get status; then
        return 0
    fi
    return 1
}

case "${1:-install}" in
    install)
        install_flow
        ;;
    status)
        status_flow
        ;;
    *)
        echo "Usage: $0 [install|status]" >&2
        exit 1
        ;;
esac
