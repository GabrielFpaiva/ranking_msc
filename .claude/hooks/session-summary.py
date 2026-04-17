#!/usr/bin/env python3
"""
Hook: session-summary — avisa se há mudanças Python sem daily note no vault.
Dispara em: Stop
"""
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

try:
    data = json.load(sys.stdin)
except Exception:
    data = {}

if data.get("stop_reason", "") not in ("end_turn", ""):
    sys.exit(0)

today = date.today().strftime("%Y-%m-%d")

PROJECT = Path("/home/nelson/projetos/Cerebro/Claude  Cerebro/psb/01 - Projects/ranking_msc")
VAULT_DAILY = Path(f"/home/nelson/projetos/Cerebro/Claude  Cerebro/psb/05 - Daily/{today}.md")

try:
    r1 = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        capture_output=True, text=True, cwd=str(PROJECT), timeout=5,
    )
    r2 = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, cwd=str(PROJECT), timeout=5,
    )
    py_changes = [f for f in (r1.stdout + r2.stdout).splitlines() if f.endswith(".py")]
except Exception:
    py_changes = []

daily_ok = VAULT_DAILY.exists()

if not py_changes and daily_ok:
    sys.exit(0)

if py_changes and not daily_ok:
    msg = (
        f"[session-summary] ⚠️  Alterações Python sem daily note no vault.\n"
        f"Arquivos: {', '.join(py_changes[:5])}"
        + (f" (+ {len(py_changes) - 5} mais)" if len(py_changes) > 5 else "")
        + f"\nCrie '05 - Daily/{today}.md' no PSB antes de encerrar."
    )
elif not daily_ok:
    msg = f"[session-summary] Lembre de criar '05 - Daily/{today}.md' no PSB."
else:
    sys.exit(0)

print(json.dumps({"systemMessage": msg}))
