# New Machine Setup

This reference is portable. Do not depend on paths or accounts from another Mac.

Two things come from the user, not from this skill:

- **The bridge code**: a fork of `huohuoer/wechat-cli` that has `send`/`reply`, `decode-image`, `history --transcribe` and `scripts/authorize_and_connect.command`. Use `$WECHAT_BRIDGE_REPO` (a GitHub `owner/name` or git URL) if set; otherwise ask the user for it. Upstream `huohuoer/wechat-cli` can read messages, but it lacks those commands and its `init` re-signs WeChat automatically, so the steps below do not apply to it.
- **The WeChat installer**: Tencent does not offer old versions for download. Ask the user where they keep the verified DMG (a private release, a NAS, another Mac). Verify it as in step 2 whatever the source.

## Requirements

- macOS, signed in to WeChat on the phone (desktop login needs a QR scan).
- Access to the bridge repository (for a private GitHub repo: `gh auth status` with an account that can read it).
- Xcode Command Line Tools (`xcode-select -p`; install with `xcode-select --install`).
- `uv` (`command -v uv`; install from https://docs.astral.sh/uv/).
- `ffmpeg` (`command -v ffmpeg`; `brew install ffmpeg`): needed for `wxgf` images and voice messages.
- The user present for: Terminal `sudo`, System Settings privacy toggles, WeChat QR login.

## Which App Needs the Permissions

macOS grants Full Disk Access and Accessibility to the app that launches the commands, not to the CLI itself:

| Agent runs in | Grant to |
|---|---|
| Claude Code / Codex CLI in Terminal | Terminal (or iTerm, etc.) |
| Claude desktop app (Code tab) | Claude |
| Codex desktop app | Codex |

After granting, quit and reopen that app.

## 1. Back Up

Quit WeChat completely, then back up (skip paths that do not exist on a fresh Mac):

```bash
backup="$HOME/wechat-backup-before-agent-channel"
mkdir -p "$backup"
ditto /Applications/WeChat.app "$backup/WeChat.app"
ditto "$HOME/Library/Containers/com.tencent.xinWeChat" "$backup/com.tencent.xinWeChat"
ditto "$HOME/Library/Group Containers/5A4RE8SF68.com.tencent.xinWeChat" "$backup/5A4RE8SF68.com.tencent.xinWeChat"
cp "$HOME/Library/Preferences/com.tencent.xinWeChat.plist" "$backup/"
```

Do not remove or overwrite chat containers before the backup is verified.

## 2. Install the Verified WeChat Version

Verified version: WeChat Mac 4.1.8 (`CFBundleVersion` 37335, `WeChatBundleVersion` 4.1.8.106). Newer versions may change the database or key layout; do not assume they work.

Check the installed version first:

```bash
defaults read /Applications/WeChat.app/Contents/Info WeChatBundleVersion
```

If it is not `4.1.8.106`, get `WeChatMac_4.1.8.dmg` from the user's archive into a download folder, for example from a private GitHub release:

```bash
dl="$HOME/Downloads/wechat-4.1.8"
mkdir -p "$dl"
gh release download <tag> -R <owner/repo> -p 'WeChatMac_4.1.8.dmg' -D "$dl"
shasum -a 256 "$dl/WeChatMac_4.1.8.dmg"
```

The hash must be exactly:

```text
972823a966cdaa1f5f0a785bc9f1219d174a75f43d30ec0fbf9ba7ab0249b2f1
```

Then confirm the app inside is Tencent's notarized original:

```bash
mnt="$(hdiutil attach -nobrowse -readonly "$dl/WeChatMac_4.1.8.dmg" | awk -F'\t' '/Volumes/{print $NF}')"
codesign -dv --verbose=2 "$mnt/WeChat.app" 2>&1 | grep -E 'Authority=Developer ID Application|TeamIdentifier'
spctl -a -vv "$mnt/WeChat.app" 2>&1 | grep source
```

Expected: `Developer ID Application: Tencent Mobile International Limited (5A4RE8SF68)`, `TeamIdentifier=5A4RE8SF68`, `source=Notarized Developer ID`. If either check fails, stop and tell the user.

Install (WeChat must be quit; the old app was backed up in step 1):

```bash
rm -rf /Applications/WeChat.app
ditto "$mnt/WeChat.app" /Applications/WeChat.app
hdiutil detach "$mnt"
```

Disable automatic updates so WeChat stays on this version:

```bash
defaults write com.tencent.xinWeChat SUEnableAutomaticChecks -bool false
defaults write com.tencent.xinWeChat SUAutomaticallyUpdate -bool false
```

Open WeChat, log in with the phone, and let it finish syncing. If an update prompt appears, choose skip/later in the UI.

## 3. Deploy the CLI

```bash
cli_dir="$HOME/wechat-local-bridge"
git clone "$WECHAT_BRIDGE_REPO" "$cli_dir"   # or: gh repo clone <owner/repo> "$cli_dir"
cd "$cli_dir"
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python 'click>=8.1,<9' 'pycryptodome>=3.19,<4' 'zstandard>=0.22,<1'
```

For voice messages (decode and transcribe), also install:

```bash
uv pip install --python .venv/bin/python pilk faster-whisper 'av<15'
```

`av<15` is required: newer `av` breaks faster-whisper. The first `--transcribe` downloads the Whisper `small` model (~480 MB) into `~/.cache/huggingface`.

`wechat-cli-local` uses `.venv/bin/python3` automatically when it exists.

Compile the key scanner for this Mac's architecture (do not rely on prebuilt binaries; the fork changes the scanner source):

```bash
cd "$cli_dir"
cc -O2 -o "wechat_cli/bin/find_all_keys_macos.$(uname -m)" wechat_cli/bin/find_all_keys_macos.c -framework Foundation
chmod 755 "wechat_cli/bin/find_all_keys_macos.$(uname -m)" wechat-cli-local scripts/*.sh scripts/*.command
./wechat-cli-local --help
```

## 4. Grant Full Disk Access

Grant Full Disk Access to the host app (table above), then restart it:

```bash
open 'x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles'
```

## 5. Re-sign WeChat and Extract Keys (user runs this)

WeChat must be fully quit. Ask the user to run this in their own Terminal and enter their password:

```bash
sudo "$HOME/wechat-local-bridge/scripts/authorize_and_connect.command"
```

The script keeps WeChat's existing entitlements, adds only `com.apple.security.get-task-allow`, re-signs `/Applications/WeChat.app` ad-hoc, launches WeChat as the console user, waits for the databases to open (up to 60 s; the user may need to log in), and writes keys to `~/.wechat-cli`. Status is in `/tmp/codex-wechat-key-scan.status`.

Validate without printing key contents:

```bash
ls -ld ~/.wechat-cli ~/.wechat-cli/config.json ~/.wechat-cli/all_keys.json
"$HOME/wechat-local-bridge/wechat-cli-local" sessions --limit 3 --format json
```

Expected modes: directory `700`, both files `600`.

## 6. Fix WeChat's Screenshot Permission

Re-signing changes WeChat's code identity, so macOS drops its Screen Recording permission and WeChat's screenshot tool reports that recording is disabled. Fix:

```bash
tccutil reset ScreenCapture com.tencent.xinWeChat
open 'x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture'
```

The user enables WeChat in the list, then quits and reopens WeChat. If WeChat is not listed, trigger its screenshot once or add `/Applications/WeChat.app` with the `+` button. Do not edit the TCC database directly.

## 7. Enable Sending (optional)

Grant Accessibility to the host app (table above), restart it, then:

```bash
"$HOME/wechat-local-bridge/wechat-cli-local" send --check-permission --format json
"$HOME/wechat-local-bridge/wechat-cli-local" send "文件传输助手" --message "test" --format json
```

The second command is a dry-run. Do a real send only after the user approves recipient and text (see `usage.md`).

## 8. Final Check

```bash
./scripts/check_local_bridge.sh --probe-read
```

All of `cli_executable`, `config_file`, `all_keys_file`, `read_probe=ok` must hold; `wechat_signature=adhoc`.

If the CLI lives somewhere other than `~/wechat-local-bridge`, link it there (`ln -s /actual/dir ~/wechat-local-bridge`) so every Agent finds it without configuration.

## Recovery

### WeChat updated itself or was re-installed

Symptom: `wechat_signature=tencent` and/or `read_probe=failed`, `task_for_pid failed`, decryption errors. The update replaced the re-signed app and may have rotated keys.

1. Check the version: `defaults read /Applications/WeChat.app/Contents/Info WeChatBundleVersion`.
2. If it is no longer `4.1.8.106`, the new version is unverified. Tell the user and either reinstall 4.1.8 (step 2; chat data stays in the containers) or try the new version knowing it may fail.
3. Re-run step 5, then step 6.
4. Re-apply the auto-update settings from step 2.

### Keys stale after re-login or account switch

Symptom: `key_scan_failed` or reads fail while the signature is still `adhoc`. Make sure WeChat is logged in and running, then re-run step 5.
