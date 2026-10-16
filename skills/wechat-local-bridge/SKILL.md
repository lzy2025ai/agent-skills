---
name: wechat-local-bridge
description: "Use when the user asks an Agent to read, search, summarize, export, or monitor local WeChat messages (including \"what did X send me\", unread messages, group digests, viewing chat images, transcribing voice messages); send a user-confirmed text through the WeChat desktop client; verify or repair the local WeChat CLI bridge (for example after a WeChat update, or WeChat's screenshot tool saying screen recording permission is off after re-signing); or set up the bridge on another Mac without uploading WeChat databases or keys."
---

# WeChat Local Bridge

This skill teaches an Agent how to use or set up a local WeChat CLI bridge on macOS (`wechat-cli-local`, a fork of [huohuoer/wechat-cli](https://github.com/huohuoer/wechat-cli) that adds sending, image decryption and voice transcription). The bridge has two surfaces:

- Read local WeChat data and produce bounded summaries or JSON/text outputs.
- Send text through the foreground WeChat desktop UI, only after explicit user confirmation.

Do not upload WeChat databases, `~/.wechat-cli/all_keys.json`, raw key material, or large raw chat exports.

## Route the Task

1. Run the check script from this skill directory:

   ```bash
   ./scripts/check_local_bridge.sh --probe-read
   ```

   It finds the CLI at `$WECHAT_CLI_PATH`, `~/wechat-local-bridge/wechat-cli-local`, or on `PATH`.

2. Route on the result:
   - `read_probe=ok`: existing bridge. Read `references/usage.md` and do the task.
   - `cli_path=not_found` and `config_dir=no`: new machine. Read `references/setup-new-machine.md`.
   - `cli_path=not_found` but `config_dir=yes`: the bridge is installed somewhere else. Ask the user where, then set `WECHAT_CLI_PATH` for the commands or link that directory to `~/wechat-local-bridge`.
   - `wechat_signature=tencent`, or `read_probe=failed` on a machine that worked before: WeChat was probably updated or re-installed. Read the "Recovery" section of `references/setup-new-machine.md`.
3. WeChat's own screenshot tool says screen recording permission is disabled (微信截图提示录屏权限未开启): caused by the re-signing. Follow step 6 of `references/setup-new-machine.md`.
4. Safety questions (modifying history, bypassing confirmation, exporting keys, writing the database): use the boundaries below and refuse unsafe writes.

## Contacts Are User Data

This skill holds no contacts. Before searching by name, look for a saved username (`wxid_...`, `...@chatroom`):

- the current project's instructions (`CLAUDE.md` / `AGENTS.md`), for contacts tied to that project, such as a client;
- `~/.wechat-cli/contacts.md`, for the user's personal contacts and groups.

When you had to search to identify a contact and the user confirms it, offer to save the username in one of those two places. Never write contacts into this skill.

## Safety Boundaries

- Never write or patch WeChat SQLite/SQLCipher databases.
- Never claim to modify already synced WeChat history. Local DB edits would not change server or recipient state and can corrupt client data.
- Never send a message unless the user explicitly specified both recipient and final text in the current task context.
- Never bypass dry-run. If name resolution is ambiguous, ask the user to choose or use the username.
- If WeChat has update, login, or blocking windows, stop the send workflow and report the blocker.
- Do not print, copy, or summarize secret key values.
- Steps that need `sudo` (re-signing WeChat, extracting keys) are run by the user in their own Terminal. Give them the exact command; do not try to obtain their password.

## Resources

- `references/usage.md`: day-to-day commands, output handling, known limits.
- `references/setup-new-machine.md`: new Mac setup, installer verification, recovery after a WeChat update.
- `scripts/check_local_bridge.sh`: safe status check; prints no key material and suppresses message contents.
