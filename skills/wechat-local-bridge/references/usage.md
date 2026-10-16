# Using the Bridge

`$CLI` below means the `cli_path` printed by `scripts/check_local_bridge.sh`. Use its absolute path.

## Ground Rules

- Resolve relative dates first: run `date '+%Y-%m-%d %H:%M:%S %Z'`, then pass explicit `--start-time "YYYY-MM-DD HH:MM:SS"` / `--end-time`.
- Use `--format json` for anything you will process.
- `history` returns 50 messages by default. Set `--limit` to cover the range you need.
- Address chats by username (`wxid_...`, `...@chatroom`) when names are duplicated or ambiguous. Find usernames with `contacts --query` or `sessions`.

## Large Results Go to a File

A busy group can produce 1000+ messages a day; printed directly, the output gets truncated and the summary silently misses part of the day. When a query may return more than ~200 messages, write it to a temporary file and process it locally:

```bash
out="$(mktemp -t wechat-history).json"
"$CLI" history "chat or username" --start-time "YYYY-MM-DD 00:00:00" --end-time "YYYY-MM-DD 23:59:59" --limit 5000 --format json > "$out"
python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["count"], len(d["messages"]))' "$out"
```

Then filter (drop stickers, red packets, pats, template welcomes) before summarizing. Delete the file when done; never upload it.

Use `stats` first to learn the volume of a range.

## Output Shape

`history` JSON: `{"chat", "username", "is_group", "count", "offset", "limit", "start_time", "end_time", "type", "messages": [...], "failures"}`. Each message is a plain string: `"[YYYY-MM-DD HH:MM] Sender: content"`.

## Common Tasks

Who messaged me / what is unread:

```bash
"$CLI" unread --limit 20 --format json
"$CLI" sessions --limit 20 --format json
```

Read one friend or group:

```bash
"$CLI" history "name or username" --start-time "YYYY-MM-DD 00:00:00" --end-time "YYYY-MM-DD 23:59:59" --limit 500 --format json
```

Only one message type (`text|image|voice|video|sticker|location|link|file|call|system`):

```bash
"$CLI" history "name or username" --type link --limit 50 --format json
```

Search:

```bash
"$CLI" search "keyword" --chat "chat A" --chat "chat B" --start-time "YYYY-MM-DD" --limit 50 --format json
```

Find a contact / list group members:

```bash
"$CLI" contacts --query "name or remark" --format json
"$CLI" members "group name or chatroom username" --format json
```

Volume and top senders for a range:

```bash
"$CLI" stats "chat or username" --start-time "YYYY-MM-DD" --end-time "YYYY-MM-DD" --format json
```

Export to Markdown or text (only when the user asks for a file, and write it where they asked):

```bash
"$CLI" export "chat or username" --format markdown --start-time "YYYY-MM-DD" --output /path/to/file.md
```

Favorites:

```bash
"$CLI" favorites --format json
```

## `new-messages` Has Shared State

`new-messages` returns only what arrived since its previous call and records progress in `~/.wechat-cli/last_check.json`. Every Agent on this Mac (Claude Code, Codex, scripts) shares that file, so a call from one Agent hides those messages from the next. For "what came in today / since X", use `unread` or `history` with an explicit time range instead. Use `new-messages` only for a single dedicated monitor.

## Images and Voice

Add `--media --decode` to `history` to get viewable files: images become `.jpg`/`.png`, voice messages become `.wav`, all under `~/.wechat-cli/decoded_images/`. Open images with your image-reading tool.

```bash
"$CLI" history "chat or username" --type image --limit 10 --media --decode --format json
```

Voice messages show as `[语音] 41秒`. To get the words, use `--transcribe` (implies `--media --decode`; local faster-whisper, roughly 10 s per message on a laptop CPU, cached afterwards as `.txt` next to the `.wav`):

```bash
WECHAT_CLI_WHISPER_HINT="<proper nouns, e.g. product or brand names>" \
  "$CLI" history "chat or username" --type voice --start-time "YYYY-MM-DD HH:MM" --transcribe --format text
```

`WECHAT_CLI_WHISPER_HINT` lists proper nouns from the conversation; without it homophones get mangled (美团 came out as 美茶 in testing). Projects can keep a ready-made hint next to their saved contacts. Still read transcripts with the chat context and fix obvious mishearings. To redo a transcript with a better hint, delete its `.txt` first.

Decrypt specific image `.dat` files directly:

```bash
"$CLI" decode-image /path/to/a.dat /path/to/b.dat --format json
```

- WeChat downloads the full image only after the user taps it. Until then only a thumbnail (`..._t.jpg`, ~150-250 px) exists. If it is too small to read, ask the user to tap the image in WeChat once, then decode again.
- The image key is derived offline the first time (usually under a second) and cached in `~/.wechat-cli/image_keys.json` (mode 600). Never print it.
- Some images are WeChat's own `wxgf` format; they are converted to `.jpg` with `ffmpeg`.
- `(本地没有语音数据)` means the voice was never downloaded to this Mac; ask the user to play it once in WeChat.
- Files (`[文件] name.xlsx`) come with their local path under `msg/file/`; read them in place, do not copy them elsewhere.
- Decrypted images and audio are the user's private data: use them locally, never upload them.

## Sending

1. Check permission: `"$CLI" send --check-permission --format json` (`reply` is an alias of `send`).
2. Dry-run (no `--confirm`):

   ```bash
   "$CLI" send "chat or username" --message "text" --format json
   ```

3. Show the user the resolved recipient and the final text. Wait for explicit approval.
4. Real send, message body via stdin:

   ```bash
   printf '%s' 'approved final text' | "$CLI" send "chat or username" --stdin --confirm --format json
   ```

5. Verify with `"$CLI" sessions --limit 5 --format json` or the WeChat window.

Sending drives the WeChat window in the foreground; the user should not type in WeChat while it runs.

## Failure Handling

- `search` misses a message you know exists (seen with recent messages): find the chat with `contacts --query` or `sessions`, then read it with `history` and a time range.
- `sessions` shows a new message but `history`/`search` does not: it may not be in the located database shard yet. Retry after a moment, or confirm in the WeChat window.
- `read_probe=failed`, `task_for_pid failed`, or decryption errors after WeChat updated itself: see "Recovery" in `setup-new-machine.md`.
- Accessibility failure on send: grant Accessibility to the app that launched the Agent (see the host table in `setup-new-machine.md`), restart that app.
- Update window or extra WeChat window: stop sending and ask the user to close or skip it.
