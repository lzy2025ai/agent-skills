# agent-skills

给 Claude Code（以及部分适用于 Codex）的开源 Skill 合集。每个 skill 是 `skills/` 下的一个目录。

Open-source skills for Claude Code. Each skill lives in its own folder under `skills/`.

## Skill 列表

| Skill | 做什么 |
|---|---|
| [session-hub](skills/session-hub/SKILL.md) | 在本机的 Claude Code 和 Codex 会话之间找记录、给跳转链接、把任务转派给某个 Claude 会话 |

## 安装

把某个 skill 目录放进（或软链到）Claude Code 的 skill 目录：

```bash
git clone https://github.com/lzy2025ai/agent-skills.git
ln -s "$(pwd)/agent-skills/skills/session-hub" ~/.claude/skills/session-hub
```

只想在某个项目里用，就链到 `<项目>/.claude/skills/`。

## session-hub 说明

**适合谁**：同时在 Claude Code 桌面版和 Codex 桌面版里开很多会话、经常想不起「那件事是在哪个会话里做的」的人。

**能做**
- 按标题、项目目录、对话内容搜两边的会话，读出当时的讨论原文。
- 给出点击即跳转的链接：Claude 桌面版会话链接；Codex 用 `codex://threads/<会话ID>`。
- 通过 Claude 桌面版自带的会话工具，给另一个 Claude 会话发消息，让它接着干。

**不能做**
- 给 Codex 会话代发消息。`codex exec resume` 在 ChatGPT 账号登录时，桌面版常用模型会被拒绝，未能实测通过。

**依赖**
- Python 3（只用标准库），macOS 上测试过。
- 发消息、生成 Claude 会话链接需要 Claude Code **桌面版**；命令行版只能查找，并用 `claude --resume` 接续。

**已知限制**
- 读取的是 Claude Code 和 Codex 的本地存储格式（`~/.claude/projects/`、`~/.codex/state_*.sqlite`、`~/.codex/sessions/`），
  不是公开接口，工具升级后可能失效。
- `codex://threads/` 链接格式来自 Codex 桌面版安装包，官方没有文档。
- 全部只读，不修改任何会话数据。

## License

MIT
