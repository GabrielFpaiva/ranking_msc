# F3-16 — Retrospectiva: Subagent-Driven Development

**Data:** 2026-04-08
**Task:** F3-16 — Dashboard Bootstrap5 + Tab Registry
**Branch entregue:** `feat/F3-16-dashboard-bootstrap5-tab-registry`
**PR:** https://github.com/GabrielFpaiva/ranking_msc/pull/52

---

## Processo utilizado

A tarefa foi executada via **Subagent-Driven Development**: plano escrito em sessão anterior,
implementado em sessão separada com subagentes especializados.

Cada task recebeu:
1. **Subagente implementador** — contexto isolado, sem histórico da sessão principal
2. **Revisor de conformidade com spec** — verifica se o que foi construído bate com o solicitado
3. **Revisor de qualidade de código** — verifica clean code, type hints, ruff, testes
4. **Ciclos de correção** quando algum revisor encontrava problemas

---

## Tasks e ciclos de revisão

| Task | Entrega | Ciclos de fix |
|------|---------|---------------|
| T1 — Tab Registry base | `TabBase` ABC + `TAB_REGISTRY` + `@register_tab` + smoke tests | 1 — sentinel defaults, validação `tab_id`, `@pytest.mark.skip` nos testes futuros |
| T2 — StatusGeralTab | Cards ERROs/ALERTAs/INFOs + tabela por dimensão | 1 — ruff I001, assertions comportamentais no teste, `logger.warning` para severidades inesperadas |
| T3 — PendenciasTab | Tabela filtrada + exportar Excel | 0 — aprovada direto |
| T4 — SaldoDevedorTab | Filtra R032, row coloring por severidade | 0 — aprovada direto |
| T5 — web_app.py | BootstrapTemplate + engine real + TAB_REGISTRY | 1 — substituir `print()` por `logger.warning()` |
| T6 — PR + backlog | PR aberto, F3-16 marcado `Concluído` | — |

---

## Desvios do plano detectados em implementação

| Plano | Implementado | Motivo |
|-------|-------------|--------|
| `pn.widgets.Tabulator` | `pn.pane.DataFrame` | jinja2 3.1.2 instalado; Tabulator exige ≥ 3.1.5 |
| `MultiSelect` (filtros) | `Select` | Dependência do Tabulator |
| `pn.extension("plotly", "tabulator")` | `pn.extension(sizing_mode="stretch_width")` | Tabulator indisponível |

> **Ação futura:** quando jinja2 for atualizado, substituir `pn.pane.DataFrame` por
> `pn.widgets.Tabulator` nas 3 abas para ganhar paginação, sorting e filtros nativos.

---

## Resultado

- 7 testes em `tests/test_tabs.py`, todos passando
- 478 testes no total, 0 falhas
- Ruff limpo em todos os arquivos novos

---

## O que o processo detectou que teria chegado ao PR sem revisão

1. **Testes commitados em estado falho** (T1) — 4 de 7 testes falhando porque as abas ainda não existiam. Fix: `@pytest.mark.skip` com reason descritivo.
2. **`TabBase` sem sentinel defaults** (T1) — atributos `tab_id`, `tab_name`, `order` sem valor padrão, tornando o decorator `@register_tab` opaco em caso de erro.
3. **`register_tab` sem validação de `tab_id`** (T1) — sem espelhar o guard do `register_rule`.
4. **Ruff I001 no `__init__.py`** (T2) — bloco de imports mal ordenado.
5. **Teste comportamental fraco** (T2) — `assert viewable is not None` sem verificar os valores reais dos contadores.
6. **`print()` em módulo principal** (T5) — violação direta do CLAUDE.md.

---

## Aprendizados para próximas tasks

- **Commitar testes que falham é anti-padrão**, mesmo para tasks futuras. Usar `@pytest.mark.skip(reason="Task X/Y")`.
- **O padrão Tab Registry** é extensível sem modificar `web_app.py` — nova aba = 1 arquivo + 1 import.
- **Dois estágios de revisão** (spec + qualidade) detectam categorias diferentes de problema. Spec encontra o que está faltando ou sobrando. Qualidade encontra como está feito.
- A **aba Pendências exporta o df filtrado** (view atual), não o total — decisão de UX a confirmar com o Rodrigo Teixeira.
