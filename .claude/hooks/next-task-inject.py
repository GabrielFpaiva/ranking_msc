#!/usr/bin/env python3
"""
Hook: next-task-inject — injeta próximas tasks pendentes do backlog.
Dispara em: UserPromptSubmit (matcher: pergunta sobre backlog/próximas tasks)
"""
import json
import sys
from pathlib import Path

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

PROJECT = Path(__file__).parent.parent.parent
BACKLOG = PROJECT / "backlog_regras_msc_completo.xlsx"

if not BACKLOG.exists():
    sys.exit(0)

try:
    import openpyxl
    wb = openpyxl.load_workbook(str(BACKLOG), read_only=True, data_only=True)
    ws = wb["Backlog Completo"]

    # Cols: ID(0) | Fase(1) | Semana(2) | Task(3) | Desc(4) | Resp(5) |
    #        Prio(6) | Horas(7) | Dep(8) | Entregavel(9) | Criterio(10) | Status(11)
    pending: list[tuple] = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue
        if not row[0]:
            continue
        status = str(row[11] or "").strip().lower()
        if status not in {"feito", "done", "concluído", "concluido"}:
            pending.append(row)

    wb.close()
except Exception as e:
    print(f"[next-task-inject] Erro ao ler backlog: {e}")
    sys.exit(0)

if not pending:
    print("[next-task-inject] Todas as tasks do backlog estão concluídas!")
    sys.exit(0)

lines = ["PRÓXIMAS TASKS PENDENTES DO BACKLOG:\n\n"]
for row in pending[:8]:
    id_, fase, semana, task, desc, resp, prio, horas, dep, *_ = (
        (row[i] if i < len(row) else None) for i in range(12)
    )
    status = row[11] if len(row) > 11 else "—"
    lines.append(
        f"• [{id_}] {task}\n"
        f"  Fase: {fase} | Prio: {prio} | Status: {status} | Horas: {horas}\n"
        f"  {str(desc or '')[:120]}{'...' if desc and len(str(desc)) > 120 else ''}\n\n"
    )

if len(pending) > 8:
    lines.append(f"... e mais {len(pending) - 8} tasks. Total pendente: {len(pending)}.\n")

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": "".join(lines),
    },
}))
