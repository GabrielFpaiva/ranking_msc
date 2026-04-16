Leia primeiro o claude.md e siga rigorosamente os padrões do projeto.

Quero que você apenas ARQUITETE a task abaixo, sem implementar nada por enquanto.

Regras:
- Leia sempre o claude.md antes de decidir qualquer coisa.
- Crie uma NOVA BRANCH específica para esta task antes de qualquer alteração, usando o padrão:
  feat/f4-03-relat-rio-com-score-e-ranking-por-categoria
  Ajuste o nome conforme a task atual, mantendo prefixo, código da task e descrição curta em kebab-case.
- Sugira também a mensagem de commit inicial no padrão:
  F4-03: implement Relatório com score e ranking por categoria
  Ajuste conforme a task atual.
- Não implemente nada nesta etapa.
- Não entregue resposta genérica.
- Considere a estrutura atual do projeto e reutilize o que já existir.
- Explique como a task deve ser feita passo a passo.
- Liste arquivos que devem ser criados, alterados ou consultados.
- Aponte regras de negócio, validações, riscos e pontos de atenção.
- Explique como garantir o critério de aceite.
- No final, entregue um plano de execução para aprovação.
- Só implemente depois da minha aprovação.

Responda nesta estrutura:
1. Entendimento da task
2. Branch a criar
3. Commit sugerido
4. Estratégia de implementação
   (inclua aqui: → Implemente seguindo as convenções do CLAUDE.md)
5. Arquivos impactados
6. Passo a passo
7. Validações e riscos
8. Como garantir o critério de aceite
9. Plano final para aprovação
   (o plano DEVE incluir como últimos passos obrigatórios, nesta ordem:
    a) Invocar skill task-validate → Skill(skill='task-validate')
       Bloqueia automaticamente se ruff/mypy/pytest falharem
    b) Após validate OK → Agent(subagent_type='code-reviewer')
    c) Após review OK  → Invocar skill task-deliver → Skill(skill='task-deliver')
       commit + push + PR (pr-body.md) + vault finalization
    Agentes disponíveis no projeto: code-reviewer, rule-implementer, session-end)

⚠️ Ao descrever regras com "N dígitos": detalhar SEMPRE como 3 checks separados:
  1. `len(val) != N → ERRO` (comprimento)
  2. `not val.isdigit() → ERRO` (formato — alfanumérico é ERRO, não ALERTA)
  3. `val not in tabela → ERRO ou ALERTA` (domínio — conforme a regra)

⚠️ Ao usar `ic_esta_informada()`: garantir que o valor chega em lowercase (`.lower()`).
  `normalize_ic` usa `.str.upper()` upstream; "NAN" não bate com "_IC_VAZIA" que tem "nan".

Task:
[F4-03 — Relatório com score e ranking por categoria]

Descrição task:
[
Adicionar aba de Score ao Excel: nota por categoria + nota geral + benchmarks.
]

Entregável:
[
outputs/reports.py com aba Score
]

Referências:
[
- Padrão de implementação: ver regras existentes em src/ranking_msc/rules/ (ex: r022.py, r024.py)
- ic_esta_informada() centralizada em src/ranking_msc/rules/base.py (não reimplementar)
- FACT_MSC_COLUMNS em src/ranking_msc/schemas.py
- ref/regras_catalogo.md — seções das regras desta task
- Depende de: F4-02
]

Critério de aceite:
[
Excel exibe notas por categoria e geral.
]
