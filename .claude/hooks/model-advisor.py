#!/usr/bin/env python3
"""
Hook: model-advisor — recomenda modelo baseado na complexidade da task.
Dispara em: UserPromptSubmit (matcher: task ID F\\d+-\\d+)
"""
import json
import re
import sys

try:
    data = json.load(sys.stdin)
    prompt = data.get("prompt", "").lower()
except Exception:
    sys.exit(0)

HIGH_PATTERNS = [
    r"\barquitetura\b",
    r"\brefactor\b.*\bcompleto\b",
    r"\bpipeline\b.*\binteiro\b",
    r"\bmigra[rç]\b",
    r"\bfase\s+\d+\b",
    r"\bf\d+-\d+\b.*\bf\d+-\d+\b",
    r"\bmúltiplas?\s+regras?\b",
    r"\bdesign\b.*\bsistema\b",
    r"\bmodelo\s+de\s+dados\b",
]
LOW_PATTERNS = [
    r"\bo que [eé]\b",
    r"\bcomo funciona\b",
    r"\bexplica\b",
    r"\bqual [eé]\b",
    r"\bstatus\b",
    r"\bgit log\b",
    r"\bgit status\b",
    r"\btypo\b",
    r"\bbacklog\b",
]
MED_PATTERNS = [
    r"\bf\d+-\d+\b",
    r"\br0\d{2}\b",
    r"\bimplementar?\b",
    r"\bcorrigir?\b",
    r"\bbug\b",
    r"\bfix\b",
    r"\bteste[s]?\b",
]

high_score = sum(1 for p in HIGH_PATTERNS if re.search(p, prompt))
low_score = sum(1 for p in LOW_PATTERNS if re.search(p, prompt))
med_score = sum(1 for p in MED_PATTERNS if re.search(p, prompt))

task_ids = re.findall(r"\bF\d+-\d+\b", prompt, re.IGNORECASE)
rule_ids = re.findall(r"\bR0\d{2}\b", prompt, re.IGNORECASE)
if len(task_ids) >= 2 or len(rule_ids) >= 3:
    high_score += 2

if high_score >= 2:
    level = "COMPLEXA"
    tip = "claude-opus-4-6  → mais poderoso, use para arquitetura/multi-task\n  Para trocar: /model opus"
elif low_score >= 2 and med_score == 0 and high_score == 0:
    level = "SIMPLES"
    tip = "claude-haiku-4-5  → ~10× mais barato, suficiente para consultas\n  Para trocar: /model haiku"
else:
    level = "MÉDIA"
    tip = "claude-sonnet-4-6  → modelo atual ✓, nada a trocar"

print(f"[model-advisor] Complexidade: {level}  →  {tip}")
