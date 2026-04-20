#!/usr/bin/env python3
"""
Hook: vault-search-inject — injeta instrução de consulta ao vault antes de codificar.
Dispara em: UserPromptSubmit (matcher: intenção de implementação)
"""
import json
import re
import sys
from datetime import date

try:
    data = json.load(sys.stdin)
    prompt = data.get("prompt", "").lower()
except Exception:
    sys.exit(0)

IMPL_PATTERNS = [
    r"\bimplementar\b",
    r"\bimplement\b",
    r"\bregra\b",
    r"\brule\b",
    r"\br0\d{2}\b",
    r"\bf\d+-\d+\b",
    r"\bcriar\b",
    r"\bcreate\b",
    r"\btask\b",
    r"\bfeature\b",
    r"\bcorrigir\b",
    r"\bbugfix\b",
    r"\bfix\b",
    r"\brefactor\b",
]

if not any(re.search(p, prompt) for p in IMPL_PATTERNS):
    sys.exit(0)

today = date.today().strftime("%Y-%m-%d")

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": (
            f"HOOK vault-search-inject: Intenção de implementação detectada.\n\n"
            "ANTES de escrever qualquer código:\n"
            "1. Leia '03 - Resources/Claude Code Workflow.md' no PSB vault — padrões de workflow\n"
            "2. Leia '03 - Resources/Nelson Tech Preferences.md' — preferências técnicas do projeto\n"
            "3. Use mcp__obsidian__* para buscar notas relevantes no vault se necessário\n\n"
            "APÓS concluir a task:\n"
            f"1. Crie/atualize '05 - Daily/{today}.md' com resumo e [[wikilinks]]\n"
            "2. Adicione log entry em '01 - Projects/Ranking MSC.md'\n"
            "3. Se descobriu padrão novo → registre em '03 - Resources/'\n\n"
            "Use mcp__obsidian__* para todas as operações no vault."
        ),
    },
}))
