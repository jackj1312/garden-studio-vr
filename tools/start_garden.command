#!/bin/bash
# Start only the garden development port. Keep this window open while editing.
set -u
cd "$(dirname "$0")/.." || exit 1
port=8450
wifi=$(/usr/sbin/ipconfig getifaddr en0 2>/dev/null || true)
children=()
stop_children() { for pid in "${children[@]}"; do kill "$pid" 2>/dev/null || true; done; }
trap stop_children EXIT
trap 'exit' INT TERM
start_if_needed() {
  local addr="$1"; shift
  if /usr/bin/curl -ksf --max-time 2 "https://$addr:$port/layout?site=house-wip&version=approved_2b" >/dev/null; then
    printf 'Garden design is running at https://%s:%s/garden/\n' "$addr" "$port"
  else
    python3 -u tools/https-serve.py "$port" "$addr" "$@" &
    children+=("$!")
    printf 'Opening the garden service at https://%s:%s/garden/\n' "$addr" "$port"
  fi
}
start_if_needed 127.0.0.1
if [[ -n "$wifi" && "$wifi" != '127.0.0.1' ]]; then start_if_needed "$wifi" --garden-lan; fi
for pid in "${children[@]}"; do wait "$pid"; done

