#!/usr/bin/env bash
# Sets up a Nexora server: the backend (Docker) and a relay, on one VPS.
# Run as root from the root of this repository:
#
#   sudo ./deploy/setup-server.sh                 # backend + relay
#   sudo ./deploy/setup-server.sh 203.0.113.10    # same, if the public IP is not detected
#
# Another relay on another VPS (only the relay; the backend stays on the first one):
#
#   sudo RELAY_ONLY=1 TOKEN_SECRET='<RELAY_TOKEN_SECRET from the first server>' ./deploy/setup-server.sh
#
# Safe to run again: existing keys, database and .env settings are kept.
set -euo pipefail
cd "$(dirname "$0")/.."

RELAY_PORT=4700
RELAY_NAME=${RELAY_NAME:-"Nexora $(hostname -s)"}
RELAY_ONLY=${RELAY_ONLY:-0}
CONFIG=/etc/nexora/relay.json

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }
die() { printf '\033[31m%s\033[0m\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "Run as root: sudo $0"
[[ -f deploy/relay/nexora-relay ]] || die "Run this from the BoostX-Server repository."

PUBLIC_IP=${1:-}
if [[ -z $PUBLIC_IP ]]; then
  PUBLIC_IP=$(curl -4 -fsS --max-time 5 https://api.ipify.org || curl -4 -fsS --max-time 5 https://ifconfig.me || true)
fi
[[ $PUBLIC_IP =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "Could not detect the public IPv4 address. Pass it: $0 <ip>"

# ---------------------------------------------------------------- packages
say "1/5 Packages"
if ! command -v iptables >/dev/null; then apt-get update -q && apt-get install -yq iptables; fi
if [[ $RELAY_ONLY != 1 ]]; then
  if ! command -v docker >/dev/null; then curl -fsSL https://get.docker.com | sh; fi
  docker compose version >/dev/null 2>&1 || apt-get install -yq docker-compose-plugin
fi
echo "ok"

# ------------------------------------------------------------------- relay
say "2/5 Relay (UDP $RELAY_PORT)"
install -m 755 deploy/relay/nexora-relay /usr/local/bin/nexora-relay
install -d -m 700 /etc/nexora
if [[ ! -f $CONFIG ]]; then
  nexora-relay init -out "$CONFIG" >/dev/null
  echo "new relay keys created"
fi
chmod 600 "$CONFIG"
json_value() { sed -n "s/.*\"$1\": *\"\([^\"]*\)\".*/\1/p" "$CONFIG"; }
if [[ -n ${TOKEN_SECRET:-} && $(json_value token_secret) != "$TOKEN_SECRET" ]]; then
  # Every relay must accept the tokens the one backend signs.
  sed -i "s|\"token_secret\": *\"[^\"]*\"|\"token_secret\": \"$TOKEN_SECRET\"|" "$CONFIG"
  echo "token secret set to the backend's"
fi
install -m 644 deploy/relay/nexora-relay.service /etc/systemd/system/nexora-relay.service
systemctl daemon-reload
systemctl enable -q nexora-relay
systemctl restart nexora-relay
sleep 1
systemctl is-active -q nexora-relay || { journalctl -u nexora-relay -n 20 --no-pager; die "The relay did not start."; }
RELAY_PUBKEY=$(nexora-relay pubkey -config "$CONFIG")
RELAY_SECRET=$(json_value token_secret)
SERVER_ENTRY="{\"id\":\"$(hostname -s)\",\"name\":\"$RELAY_NAME\",\"region\":\"\",\"address\":\"$PUBLIC_IP:$RELAY_PORT\",\"public_key\":\"$RELAY_PUBKEY\"}"
echo "running: $PUBLIC_IP:$RELAY_PORT"

# ---------------------------------------------------------------- firewall
say "3/5 Firewall"
if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
  ufw allow "$RELAY_PORT/udp" >/dev/null
  [[ $RELAY_ONLY == 1 ]] || ufw allow 8000/tcp >/dev/null
  echo "ufw: opened $RELAY_PORT/udp$([[ $RELAY_ONLY == 1 ]] || echo ' and 8000/tcp')"
else
  echo "ufw is not active; nothing to open here."
fi
echo "If your hosting provider has its own firewall in its panel, open the same ports there."

if [[ $RELAY_ONLY == 1 ]]; then
  say "Done — relay only"
  cat <<MSG
Add this server to RELAY_SERVERS in the backend's .env (on the first server),
inside the [ ], separated from the others by a comma:

  $SERVER_ENTRY

then restart the backend there:  docker compose up -d
MSG
  exit 0
fi

# ----------------------------------------------------------------- backend
say "4/5 Backend settings (.env)"
[[ -f .env ]] || { cp .env.example .env; echo "created .env from .env.example"; }
chmod 600 .env
set_env() {  # set_env KEY VALUE — replaces the line, keeps everything else
  local tmp; tmp=$(mktemp)
  grep -v "^$1=" .env > "$tmp" || true
  printf "%s='%s'\n" "$1" "$2" >> "$tmp"
  cat "$tmp" > .env && rm -f "$tmp"
}
current_jwt=$(sed -n "s/^JWT_SECRET_KEY=['\"]\{0,1\}\([^'\"]*\).*/\1/p" .env)
if [[ -z $current_jwt || $current_jwt == change-me* ]]; then
  set_env JWT_SECRET_KEY "$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  echo "generated JWT_SECRET_KEY"
fi
set_env RELAY_TOKEN_SECRET "$RELAY_SECRET"
existing_servers=$(sed -n "s/^RELAY_SERVERS='\(.*\)'$/\1/p" .env)
if [[ -z $existing_servers || $existing_servers == "[]" ]]; then
  set_env RELAY_SERVERS "[$SERVER_ENTRY]"
elif [[ $existing_servers != *"$PUBLIC_IP:$RELAY_PORT"* ]]; then
  set_env RELAY_SERVERS "${existing_servers%]},$SERVER_ENTRY]"
else
  # This relay is already listed: refresh its entry (its key may be new).
  set_env RELAY_SERVERS "$(printf '%s' "$existing_servers" | sed "s|{[^}]*\"$PUBLIC_IP:$RELAY_PORT\"[^}]*}|$SERVER_ENTRY|")"
fi
echo "RELAY_SERVERS and RELAY_TOKEN_SECRET set"

say "5/5 Backend (Docker)"
docker compose up -d --build
for _ in $(seq 1 60); do
  curl -fsS --max-time 2 http://127.0.0.1:8000/api/v1/health >/dev/null 2>&1 && break
  sleep 2
done
curl -fsS --max-time 2 http://127.0.0.1:8000/api/v1/health >/dev/null || { docker compose logs --tail 40 app; die "The backend did not come up."; }
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:8000/api/v1/relay/session \
  -H 'Content-Type: application/json' -d '{"device_id":"x"}')
[[ $code == 401 ]] || die "Unexpected answer from /relay/session: $code"
echo "backend is up"

say "Done"
cat <<MSG
Backend:  http://$PUBLIC_IP:8000/api/v1
Relay:    $PUBLIC_IP:$RELAY_PORT  ($RELAY_NAME)

Nexora.exe test builds talk to http://194.87.200.215:8000/api/v1 by default.
If this server has another address, put this line into a file api_url.txt
next to Nexora.exe:

  http://$PUBLIC_IP:8000/api/v1

Logs:  journalctl -u nexora-relay -f     docker compose logs -f app
For another relay on another VPS, run there:
  sudo RELAY_ONLY=1 TOKEN_SECRET='$RELAY_SECRET' ./deploy/setup-server.sh
(keep that secret private)
MSG
