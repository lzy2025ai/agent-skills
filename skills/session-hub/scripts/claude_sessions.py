#!/usr/bin/env python3
"""查找本机 Claude Code 会话（备用方案）。

Claude 桌面版自带会话管理工具时优先用那些工具（能给出跳转链接、能发消息）；
命令行版 Claude Code 没有这些工具时，用本脚本从本地对话记录里找会话，
再用 `claude --resume <会话ID>` 接着聊。

只读，仅用 Python 标准库。

用法：
  claude_sessions.py list   [--cwd 片段] [--limit N]
  claude_sessions.py search 关键词 [--limit N]
  claude_sessions.py show   会话ID [--messages N]

数据来源：~/.claude/projects/<目录名>/<会话ID>.jsonl（非公开格式，版本升级可能变化）。
环境变量 CLAUDE_CONFIG_DIR 可覆盖 ~/.claude。
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import sys

CLAUDE_HOME = os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude"))


def transcripts() -> list[str]:
    files = glob.glob(os.path.join(CLAUDE_HOME, "projects", "*", "*.jsonl"))
    return sorted(files, key=os.path.getmtime, reverse=True)


def text_of(message) -> str:
    content = (message or {}).get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")
    return ""


def summarize(path: str, max_messages: int = 0) -> dict:
    session_id = os.path.basename(path)[:-len(".jsonl")]
    title = ai_title = cwd = ""
    first_user = ""
    messages: list[str] = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = d.get("type")
            if kind == "custom-title":
                title = d.get("customTitle") or title
            elif kind == "ai-title":
                ai_title = d.get("aiTitle") or ai_title
            elif kind == "user" and not d.get("isSidechain"):
                cwd = cwd or d.get("cwd", "")
                text = text_of(d.get("message")).strip()
                # 跳过工具结果、系统注入和斜杠命令的回显
                if not text or text.startswith("<"):
                    continue
                first_user = first_user or text
                if max_messages:
                    messages.append(f"{d.get('timestamp', '')[:16].replace('T', ' ')} {' '.join(text.split())[:300]}")
    info = {
        "id": session_id,
        "title": title or ai_title or " ".join(first_user.split())[:80],
        "cwd": cwd,
        "updated": dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M"),
        "resume": f"claude --resume {session_id}",
    }
    if max_messages:
        info["file"] = path
        info["user_message_count"] = len(messages)
        info["recent_user_messages"] = messages[-max_messages:]
    return info


def main() -> int:
    ap = argparse.ArgumentParser(description="查找本机 Claude Code 会话")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_list = sub.add_parser("list")
    p_list.add_argument("--cwd")
    p_list.add_argument("--limit", type=int, default=20)
    p_search = sub.add_parser("search")
    p_search.add_argument("keyword")
    p_search.add_argument("--limit", type=int, default=20)
    p_show = sub.add_parser("show")
    p_show.add_argument("id")
    p_show.add_argument("--messages", type=int, default=15)
    args = ap.parse_args()

    if args.cmd == "show":
        matches = [p for p in transcripts() if os.path.basename(p) == f"{args.id}.jsonl"]
        result = summarize(matches[0], args.messages) if matches else {"error": f"找不到会话 {args.id}"}
    else:
        result = []
        escaped = json.dumps(getattr(args, "keyword", "") or "")[1:-1]
        for path in transcripts():
            if args.cmd == "search":
                with open(path, encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
                idx = content.find(args.keyword)
                if idx < 0:
                    idx = content.find(escaped)
                if idx < 0:
                    continue
                info = summarize(path)
                snippet = content[max(0, idx - 80): idx + len(args.keyword) + 80]
                info["snippet"] = " ".join(snippet.replace("\\n", " ").split())[:240]
            else:
                info = summarize(path)
                if args.cwd and args.cwd not in info["cwd"]:
                    continue
            result.append(info)
            if len(result) >= args.limit:
                break

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
