#!/usr/bin/env python3
"""
Hook: branch-guard — bloqueia commit/push em main ou master.
Dispara em: PreToolUse(Bash)
"""
import json
import re
import subprocess
import sys

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

tool_input = data.get("tool_input") or data.get("input") or {}
command = str(tool_input.get("command") or "")

if not re.search(r"\bgit\s+(commit|push)\b", command):
    sys.exit(0)

try:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        timeout=5,
        cwd=str(__file__).split("/.claude/")[0],
    )
    branch = result.stdout.strip()
except Exception:
    sys.exit(0)

if branch.lower() not in {"main", "master"}:
    sys.exit(0)

print(json.dumps({
    "continue": False,
    "stopReason": (
        f"[branch-guard] BLOQUEADO: branch atual é '{branch}'. "
        "Crie uma branch de feature primeiro: git checkout -b feat/<descricao>"
    ),
}))
