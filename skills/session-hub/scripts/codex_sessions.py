#!/usr/bin/env python3
"""查找本机 Codex 会话，输出可点击跳转的 codex:// 链接。

只读：会话索引库以只读模式打开，不改 Codex 的任何数据。
仅用 Python 标准库。

用法：
  codex_sessions.py list   [--cwd 片段] [--limit N] [--archived]
  codex_sessions.py search 关键词 [--deep] [--limit N] [--archived]
  codex_sessions.py show   会话ID [--messages N]
  codex_sessions.py open   会话ID          # macOS：直接唤起 Codex 打开该会话

数据来源（Codex 桌面版 / CLI 的本地存储，非公开接口，版本升级可能变化）：
  ~/.codex/state_*.sqlite 的 threads 表  —— 标题、目录、时间、归档、置顶
  ~/.codex/sessions/年/月/日/rollout-*.jsonl —— 完整对话记录
环境变量 CODEX_HOME 可覆盖 ~/.codex。
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import sqlite3
import subprocess
import sys

CODEX_HOME = os.path.expanduser(os.environ.get("CODEX_HOME", "~/.codex"))
UUID_RE = re.compile(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jsonl$")
# 自动注入的上下文块，不是用户真正说的话
INJECTED_PREFIXES = ("<", "# AGENTS.md", "# Files mentioned", "PLEASE IMPLEMENT")


def link(thread_id: str) -> str:
    return f"codex://threads/{thread_id}"


def fmt_ts(value) -> str:
    if not value:
        return "-"
    value = int(value)
    if value > 10**12:
        value //= 1000
    return dt.datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M")


def state_db() -> str | None:
    dbs = sorted(glob.glob(os.path.join(CODEX_HOME, "state_*.sqlite")),
                 key=lambda p: int(re.search(r"state_(\d+)", p).group(1)), reverse=True)
    return dbs[0] if dbs else None


def connect():
    path = state_db()
    if not path:
        return None
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def columns(conn) -> set[str]:
    return {row[1] for row in conn.execute("PRAGMA table_info(threads)")}


def clean_text(text: str) -> str:
    """去掉桌面版注入的环境块，只留用户的请求。"""
    marker = "## My request:"
    if marker in text:
        text = text.split(marker, 1)[1]
    return " ".join(text.split())


def row_to_dict(row, cols) -> dict:
    title = row["title"] or ""
    if "name" in cols and row["name"]:
        title = row["name"]
    return {
        "id": row["id"],
        "title": clean_text(title)[:120],
        "cwd": row["cwd"],
        "updated": fmt_ts(row["updated_at_ms"] if "updated_at_ms" in cols and row["updated_at_ms"] else row["updated_at"]),
        "archived": bool(row["archived"]),
        "pinned": bool(row["is_pinned"]) if "is_pinned" in cols else False,
        "link": link(row["id"]),
    }


def query_threads(where: str = "", params: tuple = (), limit: int = 20, archived: bool = False) -> list[dict]:
    conn = connect()
    if conn is None:
        return []
    cols = columns(conn)
    clauses = [] if archived else ["archived = 0"]
    if "preview" in cols:
        clauses.append("preview <> ''")  # 与 Codex 侧边栏一致：没有内容的空会话不显示
    if where:
        clauses.append(where)
    order = "updated_at_ms" if "updated_at_ms" in cols else "updated_at"
    sql = "SELECT * FROM threads"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += f" ORDER BY {order} DESC LIMIT ?"
    rows = conn.execute(sql, (*params, limit)).fetchall()
    return [row_to_dict(r, cols) for r in rows]


def rollout_files() -> list[str]:
    files = glob.glob(os.path.join(CODEX_HOME, "sessions", "*", "*", "*", "rollout-*.jsonl"))
    files += glob.glob(os.path.join(CODEX_HOME, "archived_sessions", "rollout-*.jsonl"))
    return sorted(files, key=os.path.getmtime, reverse=True)


def rollout_for(thread_id: str) -> str | None:
    conn = connect()
    if conn is not None:
        row = conn.execute("SELECT rollout_path FROM threads WHERE id = ?", (thread_id,)).fetchone()
        if row and row[0] and os.path.exists(row[0]):
            return row[0]
    for path in rollout_files():
        if path.endswith(f"{thread_id}.jsonl"):
            return path
    return None


def user_messages(path: str) -> list[tuple[str, str]]:
    out = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            p = d.get("payload") or {}
            if d.get("type") != "response_item" or p.get("type") != "message" or p.get("role") != "user":
                continue
            text = "".join(c.get("text", "") for c in p.get("content", []) if isinstance(c, dict))
            raw = text.strip()
            if "## My request:" not in raw and raw.startswith(INJECTED_PREFIXES):
                continue
            text = clean_text(raw)
            if text:
                out.append((d.get("timestamp", "")[:16].replace("T", " "), text))
    return out


def deep_search(keyword: str, limit: int) -> list[dict]:
    """在完整对话记录里逐字搜，返回命中会话和一小段上下文。"""
    hits = []
    for path in rollout_files():
        m = UUID_RE.search(path)
        if not m:
            continue
        with open(path, encoding="utf-8", errors="replace") as fh:
            content = fh.read()
        idx = content.find(keyword)
        if idx < 0:
            # 记录里中文可能被转义成 \uXXXX
            escaped = json.dumps(keyword)[1:-1]
            idx = content.find(escaped)
            if idx < 0:
                continue
        snippet = content[max(0, idx - 80): idx + len(keyword) + 80]
        snippet = snippet.replace("\\n", " ").replace('\\"', '"')
        hits.append({"id": m.group(1), "file": path, "snippet": " ".join(snippet.split())[:240], "link": link(m.group(1))})
        if len(hits) >= limit:
            break
    # 补上标题
    conn = connect()
    if conn is not None:
        cols = columns(conn)
        for hit in hits:
            row = conn.execute("SELECT * FROM threads WHERE id = ?", (hit["id"],)).fetchone()
            if row:
                hit.update({k: v for k, v in row_to_dict(row, cols).items() if k in ("title", "cwd", "updated", "archived")})
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description="查找本机 Codex 会话")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="最近的会话")
    p_list.add_argument("--cwd", help="按项目目录片段过滤")
    p_list.add_argument("--limit", type=int, default=20)
    p_list.add_argument("--archived", action="store_true", help="包含已归档")

    p_search = sub.add_parser("search", help="按关键词找会话")
    p_search.add_argument("keyword")
    p_search.add_argument("--deep", action="store_true", help="搜完整对话内容（慢），默认只搜标题和首条消息")
    p_search.add_argument("--limit", type=int, default=20)
    p_search.add_argument("--archived", action="store_true")

    p_show = sub.add_parser("show", help="看某个会话的基本信息和用户说过的话")
    p_show.add_argument("id")
    p_show.add_argument("--messages", type=int, default=15, help="显示最近多少条用户消息")

    p_open = sub.add_parser("open", help="在 Codex 桌面版中打开（macOS）")
    p_open.add_argument("id")

    args = ap.parse_args()

    if args.cmd == "list":
        where, params = ("cwd LIKE ?", (f"%{args.cwd}%",)) if args.cwd else ("", ())
        result = query_threads(where, params, args.limit, args.archived)
    elif args.cmd == "search":
        if args.deep:
            result = deep_search(args.keyword, args.limit)
        else:
            conn = connect()
            fields = ["title"]
            if conn is not None:
                cols = columns(conn)
                fields += [f for f in ("name", "first_user_message", "preview") if f in cols]
            where = "(" + " OR ".join(f"{f} LIKE ?" for f in fields) + ")"
            result = query_threads(where, tuple(f"%{args.keyword}%" for _ in fields), args.limit, args.archived)
    elif args.cmd == "show":
        conn = connect()
        info = {"id": args.id, "link": link(args.id)}
        if conn is not None:
            row = conn.execute("SELECT * FROM threads WHERE id = ?", (args.id,)).fetchone()
            if row:
                info = row_to_dict(row, columns(conn))
        path = rollout_for(args.id)
        info["file"] = path
        if path:
            msgs = user_messages(path)
            info["user_message_count"] = len(msgs)
            info["recent_user_messages"] = [f"{t} {m[:300]}" for t, m in msgs[-args.messages:]]
        result = info
    else:  # open
        if sys.platform != "darwin":
            print(json.dumps({"error": "仅支持 macOS，请手动打开链接", "link": link(args.id)}, ensure_ascii=False))
            return 1
        subprocess.run(["open", link(args.id)], check=True)
        result = {"opened": link(args.id)}

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
