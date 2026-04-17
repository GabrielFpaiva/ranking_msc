#!/usr/bin/env python3
"""
Hook: vault-finalize-inject — injeta checklist de atualização do vault ao ler task.md.
Dispara em: PostToolUse(Read)
"""
import json
import sys
from datetime import date

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

tool_input = data.get("tool_input") or data.get("input") or {}
file_path = str(tool_input.get("file_path") or tool_input.get("path") or "")

if not file_path.lower().endswith("task.md"):
    sys.exit(0)

today = date.today().strftime("%Y-%m-%d")

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": (
            f"HOOK vault-finalize-inject: task.md lido — checklist de finalização ativo.\n\n"
            "AO CONCLUIR esta task (antes de encerrar), OBRIGATÓRIO:\n"
            f"1. Crie/atualize '05 - Daily/{today}.md' com resumo e [[wikilinks]]\n"
            "2. Adicione log entry em '01 - Projects/Ranking MSC.md'\n"
            "3. Se descobriu padrão novo → '03 - Resources/'\n"
            "4. Se tomou decisão técnica → documente no CLAUDE.md do projeto\n\n"
            "Use mcp__obsidian__* para todas as operações no vault."
        ),
    },
}))
