#!/usr/bin/env python3
"""
Hook: lint-on-write — roda ruff + mypy após editar qualquer .py.
Dispara em: PostToolUse(Write|Edit)
"""
import json
import subprocess
import sys
from pathlib import Path

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

tool_input = data.get("tool_input") or data.get("input") or {}
file_path = str(tool_input.get("file_path") or tool_input.get("path") or "")

if not file_path.endswith(".py"):
    sys.exit(0)

path = Path(file_path)
if not path.exists():
    sys.exit(0)

# Localiza .venv subindo na árvore de diretórios (Linux: bin/python)
venv_python = None
for parent in [path.parent, *path.parents]:
    for candidate in [
        parent / ".venv" / "bin" / "python",
        parent / "venv" / "bin" / "python",
    ]:
        if candidate.exists():
            venv_python = candidate
            break
    if venv_python:
        break

if venv_python is None:
    sys.exit(0)

errors: list[str] = []

for tool, args in [
    ("ruff", [str(venv_python), "-m", "ruff", "check", str(path), "--output-format=concise"]),
    ("mypy", [str(venv_python), "-m", "mypy", str(path), "--no-error-summary"]),
]:
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=60)
        if r.returncode != 0 and r.stdout.strip():
            errors.append(f"{tool.upper()}:\n{r.stdout.strip()}")
    except Exception:
        pass

if errors:
    msg = f"[lint-on-write] Erros em {path.name} — corrija antes de continuar:\n\n"
    msg += "\n\n".join(errors)
    print(json.dumps({
        "systemMessage": msg,
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": f"HOOK lint-on-write: erros de lint encontrados em {path.name}. "
                                 "Corrija antes de prosseguir:\n\n" + "\n\n".join(errors),
        },
    }))
