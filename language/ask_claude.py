#!/usr/bin/env python
"""
把果蝇“第一句话”原样发给 Claude Opus 5，用本机 Claude Code 的登录配置（claude -p），不另配 API key。
  * 提示词 = results/language/first_sentence.json 里的 sentence，一字不改；
  * 在项目目录之外新建的空临时目录里运行（Claude Code 会从运行目录往上找 CLAUDE.md；
    第一次放在项目内的空文件夹里，结果读到了本项目的 CLAUDE.md，回复被污染，存档在 claude_reply_contaminated.json），
    只加载用户级设置（--setting-sources user），关掉所有工具；
  * 系统提示词换成一句中性的“你是 Claude。”，否则会带上 Claude Code 默认的编程助手设定；
  * 不保存会话（--no-session-persistence），输出 JSON 原样存档。
输出 results/language/claude_reply.json
用法：python language/ask_claude.py
"""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "language"
MODEL = "claude-opus-5"
SYSTEM = "你是 Claude。"
TOOLS_OFF = "Bash Edit Write Read Glob Grep WebFetch WebSearch NotebookEdit Task Agent"


def main():
    fs = json.loads((OUT / "first_sentence.json").read_text())
    sentence = fs["sentence"]
    cwd = Path(tempfile.mkdtemp(prefix="fly_says_"))
    assert ROOT not in cwd.parents
    cmd = [shutil.which("claude") or "claude", "-p", sentence, "--model", MODEL, "--output-format", "json",
           "--no-session-persistence", "--setting-sources", "user", "--system-prompt", SYSTEM, "--disallowedTools", TOOLS_OFF]
    print("发送：", sentence, flush=True)
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        print("claude 退出码", p.returncode, p.stderr[-2000:])
        raise SystemExit(1)
    reply = json.loads(p.stdout)
    record = dict(sentence_sent=sentence, model_requested=MODEL, system_prompt=SYSTEM, disallowed_tools=TOOLS_OFF,
                  cwd=str(cwd), command=" ".join(["claude", "-p", "<sentence>", "--model", MODEL, "--output-format", "json", "--no-session-persistence", "--setting-sources", "user",
                                    "--system-prompt", f'"{SYSTEM}"', "--disallowedTools", f'"{TOOLS_OFF}"']),
                  reply_text=reply.get("result"), raw=reply)
    (OUT / "claude_reply.json").write_text(json.dumps(record, ensure_ascii=False, indent=1))
    print("Opus 5 回复：\n" + str(reply.get("result")), flush=True)
    print("模型用量：", json.dumps(reply.get("modelUsage", reply.get("usage", {})), ensure_ascii=False)[:600])


if __name__ == "__main__":
    main()
