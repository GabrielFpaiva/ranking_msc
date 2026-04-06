# Fase 3 — Plano de Implementação

**Status:** Em andamento — F3-01 a F3-11 concluídas (2026-04-06)
**Depende de:** Fase 2 (concluída)
**Referência do backlog:** F3-01 a F3-16

---

## Resumo da Fase 2 (concluída)

| Task | Entrega | Status |
|---|---|---|
| F2-11 | `io/ref_loader.py` — carregamento PCASP + domínios com cache | ✅ |
| F2-12 | `rules/r030.py` — Fechamento patrimonial D=C | ✅ |
| F2-13 | `rules/r010.py` — Conta existe no PCASP | ✅ |
| F2-14 | `rules/r021.py` — PO válido (5 dígitos + tabela) | ✅ |
| F2-15 | `rules/r003.py` + `r004.py` — Tipo_valor e Natureza_valor válidos | ✅ |
| F2-16 | `scripts/run_pipeline.py` — CLI de execução | ✅ |
| F2-17 | Testes unitários para todas as regras piloto | ✅ |
| F2-18 | `tests/test_integration.py` — pipeline ponta a ponta | ✅ |
| F2-19 | Execução com CSVs reais (2025-11 e 2025-12) | ✅ |
| F2-20 | `outputs/logs.py` — logging JSON Lines estruturado | ✅ |
| F2-21 | `outputs/reports.py` — Excel refinado (cabeçalhos PT, cores, largura automática) | ✅ |
| F2-22 | `schemas.py` + `ic_normalize.py` — 9 tipos IC per STN 642/2026 (adição do DC) | ✅ |
| F2-23 | `io/ref_loader.py` — tabelas de domínio completas | ✅ |
| F2-24 | README atualizado + este documento | ✅ |

### Estado do pipeline ao entrar na Fase 3

- **190 testes** passando (`pytest`), sem falhas em `ruff` ou `mypy`
- **5 regras piloto** ativas: R003, R004, R010, R021, R030
- **Execução validada** com dados reais do SICONFI 2507507EX (competências 2025-11 e 2025-12)
- **Outputs gerados:** Parquet, Excel (Resumo + Pendências), log JSON Lines
- **9 tipos IC** normalizados: PO, FP, DC, FS, FR, CO, NR, ND, AI

---

## O que é a Fase 3

Implementação do **catálogo completo de regras** de validação MSC (R001–R070).

A infraestrutura está pronta — cada nova regra segue o padrão já estabelecido:
1. Criar `src/ranking_msc/rules/r<NNN>.py` com `@register_rule`
2. Importar em `src/ranking_msc/rules/__init__.py`
3. Habilitar em `config/settings.yaml`
4. Adicionar testes em `tests/test_r<NNN>.py`

---

## Tasks F3-01 a F3-16

| ID | Task | Entregável | Depende de | Status |
|---|---|---|---|---|
| F3-01 | Implementar R001–R005 (Estrutura do arquivo) | `rules/estrutura/` (5 regras) | — | ✅ Concluída |
| F3-02 | Implementar R011–R012 (PCASP nível e status) | `rules/r011.py` + `r012.py` | F2-11 | ✅ Concluída |
| F3-03 | Implementar R020 (Conjunto IC correto) | `rules/r020.py` | F2-11, F2-22 | ✅ Concluída (2026-03-31) |
| F3-04 | Implementar R080–R081 (Formato CONTA e IC) | `rules/r080.py` + `r081.py` | — | ✅ Concluída (2026-03-31) |
| F3-05 | Implementar R022–R023 (FP e DC) | `rules/r022.py` + `r023.py` | F2-22 | ✅ Concluída (2026-03-31) |
| F3-06 | Implementar R024–R025 (FR e CO) | `rules/r024.py` + `r025.py` | F2-11 | ✅ Concluída (2026-04-02) PR #35 |
| F3-07 | Implementar R026–R028 (NR, ND, FS) | `rules/r026.py` + `r027.py` + `r028.py` | F2-11 | ✅ Concluída (2026-04-02) PR #36 |
| F3-08 | Implementar R029 (AI — Ano Inscrição RP) | `rules/r029.py` | — | ✅ Concluída |
| F3-09 | Implementar R031 (SF = SI + Movimentos) | `rules/r031.py` | — | ✅ Concluída PR #43 |
| F3-10 | Implementar R032 (Natureza saldo compatível) | `rules/r032.py` | F2-11 | ✅ Concluída (2026-04-06) 343 testes |
| F3-11 | Implementar R070 (Duplicidade) | `rules/r070.py` | — | ✅ Concluída (2026-04-06) PR #44, 358 testes |
| F3-12 | Testes integração + rodar todas regras em CSV real | `tests/test_integration_f3.py` | F3-01 a F3-11 | ✅ Concluída (2026-04-06) PR #45, 382 testes |
| F3-13 | Implementar R040–R043 (Completude) | `rules/completude/` | — | A Fazer |
| F3-14 | Implementar R050–R052 (Interconta) | `rules/interconta/` | — | A Fazer |
| F3-15 | Implementar R060 (FP vs IND_SF) | `rules/r060.py` | F2-11 | A Fazer |
| F3-16 | Refinar relatório com todas regras + categorias | `outputs/reports.py` atualizado | F3-12 | A Fazer |

---

## Arquitetura existente — onde plugar novas regras

```
src/ranking_msc/
├── rules/
│   ├── base.py          ← Rule (ABC) + @register_rule + RULE_REGISTRY
│   ├── r003.py          ← exemplo de regra simples (verificação de domínio)
│   ├── r010.py          ← exemplo de regra com ref_loader (consulta PCASP)
│   └── r030.py          ← exemplo de regra com agregação (groupby)
├── io/
│   └── ref_loader.py    ← load_pcasp(), load_tabela_po/fr/co/... (cache em módulo)
└── schemas.py           ← FACT_MSC_COLUMNS, FACT_RESULTADO_REGRAS_COLUMNS
```

**Padrão de uma regra com validação de domínio:**

```python
from ranking_msc.io.ref_loader import load_tabela_fr
from ranking_msc.rules.base import Rule, register_rule

@register_rule
class R024(Rule):
    rule_id = "R024"
    rule_name = "FR válido"
    dimensao = "Domínio"

    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        tabela = load_tabela_fr()
        codigos_validos = set(tabela["codigo"])
        issues = []
        for _, row in df[df["fr"] != ""].iterrows():
            if row["fr"] not in codigos_validos:
                issues.append({
                    "severidade": "ERRO",
                    "conta_contabil": row["conta"],
                    "descricao": f"FR '{row['fr']}' não existe na tabela oficial",
                    "valor_esperado": "código em tabela_fr.csv",
                    "valor_encontrado": row["fr"],
                    "competencia": context.competencia,
                })
        return self.build_issues(issues)
```

---

## Referências

- `ref/regras_catalogo.md` — especificação completa de todas as regras R001–R111
- `ref/resultados_piloto.md` — resultados da execução com dados reais (Fase 2)
- `CLAUDE.md` — convenções, padrões e checklist de qualidade
- `ref/2026_Anexo_I_Portaria_STN_642_Regras_Gerais_MSC.pdf` — portaria com regras gerais MSC
- `ref/2026_Anexo_II_Portaria_STN_642_Leiaute_MSC_16012026.xlsx` — leiaute MSC 2026
