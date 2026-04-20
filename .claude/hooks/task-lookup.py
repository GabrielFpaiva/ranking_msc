#!/usr/bin/env python3
"""
Hook: task-lookup — lê backlog Excel, monta task.md com spec completa + instrução de planejamento.
Dispara em: UserPromptSubmit (matcher: task ID F\\d+-\\d+)

Backlog: backlog_regras_msc_completo.xlsx
  - Aba "Backlog Completo": ID | Fase | Semana | Task | Descrição Detalhada | Resp. |
                             Prioridade | Horas | Depende de | Entregável | Critério de Aceite | Status
  - Aba "Catálogo de Regras": ID Regra | Categoria | Nome da Regra | Severidade |
                               Descrição Funcional | Lógica de Validação | Dados de Entrada |
                               Resultado Esperado (OK) | Resultado Esperado (ERRO) |
                               Tabela Referência | Dependências | Prioridade Impl.
"""
import json
import re
import sys
from pathlib import Path

try:
    data = json.load(sys.stdin)
    prompt = data.get("prompt", "")
except Exception:
    sys.exit(0)

task_ids = re.findall(r"\bF\d+-\d+\b", prompt, re.IGNORECASE)
if not task_ids:
    sys.exit(0)

PROJECT = Path(__file__).parent.parent.parent
BACKLOG = PROJECT / "backlog_regras_msc_completo.xlsx"

if not BACKLOG.exists():
    print(f"[task-lookup] Backlog não encontrado: {BACKLOG}")
    sys.exit(0)

try:
    import openpyxl
    wb = openpyxl.load_workbook(str(BACKLOG), read_only=True, data_only=True)

    backlog_rows: dict[str, tuple] = {}
    ws_backlog = wb["Backlog Completo"]
    for i, row in enumerate(ws_backlog.iter_rows(values_only=True)):
        if i == 0:
            continue
        if row[0]:
            backlog_rows[str(row[0]).strip().upper()] = row

    catalog_rows: dict[str, tuple] = {}
    ws_catalog = wb["Catálogo de Regras"]
    for i, row in enumerate(ws_catalog.iter_rows(values_only=True)):
        if i == 0:
            continue
        if row[0]:
            catalog_rows[str(row[0]).strip().upper()] = row

    wb.close()
except Exception as e:
    print(f"[task-lookup] Erro ao ler backlog: {e}")
    sys.exit(0)

lines: list[str] = []

for tid in task_ids:
    tid_upper = tid.upper()
    row = backlog_rows.get(tid_upper)
    if not row:
        print(f"[task-lookup] Task {tid_upper} não encontrada no backlog.")
        continue

    id_, fase, semana, task, desc, resp, prio, horas, dep, entregavel, criterio, status = (
        (row[i] if i < len(row) else None) for i in range(12)
    )

    lines.append(f"# Task {id_} — {task}\n\n")
    lines.append(f"**Fase:** {fase} | **Semana:** {semana} | **Prioridade:** {prio} | **Status:** {status}\n\n")
    lines.append(f"**Responsável:** {resp} | **Horas estimadas:** {horas}\n\n")
    lines.append(f"**Depende de:** {dep or '—'}\n\n")
    lines.append(f"## Descrição\n\n{desc}\n\n")
    lines.append(f"## Entregável\n\n{entregavel}\n\n")
    lines.append(f"## Critério de Aceite\n\n{criterio}\n\n")

    # Regras citadas na task — injeta spec do catálogo
    rule_ids = re.findall(r"\bR\d{3}\b", f"{desc} {entregavel} {criterio}")
    if rule_ids:
        lines.append("## Especificação das Regras\n\n")
        for rid in sorted(set(rule_ids)):
            cat = catalog_rows.get(rid.upper())
            if cat:
                _, categoria, nome, severidade, desc_func, logica, dados_entrada, ok, erro, tabela_ref, *_ = (
                    (cat[i] if i < len(cat) else None) for i in range(12)
                )
                lines.append(f"### {rid} — {nome} ({severidade})\n\n")
                lines.append(f"**Categoria:** {categoria}\n\n")
                lines.append(f"**Descrição:** {desc_func}\n\n")
                if logica:
                    lines.append(f"**Lógica:**\n```\n{logica}\n```\n\n")
                lines.append(f"**Dados de entrada:** {dados_entrada}\n\n")
                lines.append(f"**OK:** {ok}\n\n**ERRO:** {erro}\n\n")
                if tabela_ref:
                    lines.append(f"**Tabela de referência:** {tabela_ref}\n\n")

    lines.append("---\n\n")

if not lines:
    sys.exit(0)

lines.append(
    "## Instrução de Planejamento\n\n"
    "Leia primeiro o CLAUDE.md e siga rigorosamente os padrões do projeto.\n\n"
    "Quero que você apenas ARQUITETE a task acima, sem implementar nada por enquanto.\n\n"
    "Regras:\n"
    "- Leia sempre o CLAUDE.md antes de decidir qualquer coisa.\n"
    "- Crie uma NOVA BRANCH específica para esta task antes de qualquer alteração, "
    "usando o padrão: `feat/F3-XX-descricao-curta-em-kebab-case`\n"
    "- Sugira também a mensagem de commit inicial no padrão: `F3-XX: descrição curta em inglês`\n"
    "- Não implemente nada nesta etapa.\n"
    "- Não entregue resposta genérica.\n"
    "- Considere a estrutura atual do projeto e reutilize o que já existir.\n"
    "- Explique como a task deve ser feita passo a passo.\n"
    "- Liste arquivos que devem ser criados, alterados ou consultados.\n"
    "- Aponte regras de negócio, validações, riscos e pontos de atenção.\n"
    "- Explique como garantir o critério de aceite.\n"
    "- No final, entregue um plano de execução para aprovação.\n"
)

task_md = PROJECT / "task.md"
task_md.write_text("".join(lines), encoding="utf-8")

found = [tid.upper() for tid in task_ids if tid.upper() in backlog_rows]
print(json.dumps({
    "systemMessage": f"[task-lookup] task.md gerado para: {', '.join(found)}",
    "hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": (
            f"HOOK task-lookup: task.md foi atualizado com a spec de {', '.join(found)}. "
            "Leia o arquivo task.md antes de responder — ele contém descrição completa, "
            "entregável, critério de aceite e spec das regras envolvidas."
        ),
    },
}))
