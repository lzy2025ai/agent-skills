#!/bin/sh
set -eu

CLI_PATH="${WECHAT_CLI_PATH:-}"
PROBE_READ=0

for arg in "$@"; do
  case "$arg" in
    --probe-read)
      PROBE_READ=1
      ;;
    --help|-h)
      printf '%s\n' "usage: check_local_bridge.sh [--probe-read]"
      printf '%s\n' "Set WECHAT_CLI_PATH=/absolute/path/to/wechat-cli-local when auto-detection cannot find it."
      exit 0
      ;;
    *)
      printf '%s\n' "unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

print_kv() {
  printf '%s=%s\n' "$1" "$2"
}

file_mode() {
  if [ -e "$1" ]; then
    stat -f '%Lp' "$1" 2>/dev/null || stat -c '%a' "$1" 2>/dev/null || printf 'unknown'
  else
    printf 'missing'
  fi
}

# Default install location is ~/wechat-local-bridge (setup links other locations there).
if [ -z "$CLI_PATH" ]; then
  for candidate in \
    "$HOME/wechat-local-bridge/wechat-cli-local" \
    "$(command -v wechat-cli-local 2>/dev/null || true)"; do
    if [ -n "$candidate" ] && [ -x "$candidate" ]; then
      CLI_PATH="$candidate"
      break
    fi
  done
fi

print_kv timezone "$(date '+%Z')"
print_kv cli_path "${CLI_PATH:-not_found}"

if [ -n "$CLI_PATH" ] && [ -x "$CLI_PATH" ]; then
  print_kv cli_executable yes
else
  print_kv cli_executable no
fi

if [ -d "$HOME/.wechat-cli" ]; then
  print_kv config_dir yes
  print_kv config_dir_mode "$(file_mode "$HOME/.wechat-cli")"
else
  print_kv config_dir no
fi

for path in "$HOME/.wechat-cli/config.json" "$HOME/.wechat-cli/all_keys.json"; do
  key="$(basename "$path" .json)"
  if [ -f "$path" ]; then
    print_kv "${key}_file" yes
    print_kv "${key}_mode" "$(file_mode "$path")"
  else
    print_kv "${key}_file" no
  fi
done

if [ -d /Applications/WeChat.app ]; then
  version="$(defaults read /Applications/WeChat.app/Contents/Info CFBundleShortVersionString 2>/dev/null || true)"
  build="$(defaults read /Applications/WeChat.app/Contents/Info CFBundleVersion 2>/dev/null || true)"
  bundle="$(defaults read /Applications/WeChat.app/Contents/Info WeChatBundleVersion 2>/dev/null || true)"
  print_kv wechat_version "${version:-unknown}"
  print_kv wechat_build "${build:-unknown}"
  print_kv wechat_bundle "${bundle:-unknown}"
  # adhoc = re-signed for key access (expected); tencent = original signature, e.g. after an update
  sig="$(codesign -dv /Applications/WeChat.app 2>&1 || true)"
  case "$sig" in
    *Signature=adhoc*) print_kv wechat_signature adhoc ;;
    *TeamIdentifier=5A4RE8SF68*) print_kv wechat_signature tencent ;;
    *) print_kv wechat_signature unknown ;;
  esac
else
  print_kv wechat_app no
fi

tmp_dir="$(mktemp -d -t wechat-local-bridge)"
trap 'rm -rf "$tmp_dir"' EXIT HUP INT TERM

if [ -n "$CLI_PATH" ] && [ -x "$CLI_PATH" ]; then
  if "$CLI_PATH" send --check-permission --format json >"$tmp_dir/acc" 2>/dev/null; then
    if grep -q '"allowed": true' "$tmp_dir/acc"; then
      print_kv accessibility_allowed yes
    else
      print_kv accessibility_allowed no
    fi
  else
    print_kv accessibility_allowed check_failed
  fi
fi

if [ "$PROBE_READ" -eq 1 ] && [ -n "$CLI_PATH" ] && [ -x "$CLI_PATH" ]; then
  if "$CLI_PATH" sessions --limit 1 --format json >/dev/null 2>"$tmp_dir/err"; then
    print_kv read_probe ok
  else
    print_kv read_probe failed
    # first error line only, to classify the failure; never message contents
    print_kv read_probe_error "$(head -n 1 "$tmp_dir/err" | cut -c1-160)"
  fi
fi
