# Inventário de Legado — 2026-05-19

Status curto do legado remanescente após o cutover definitivo da interface
Panel concluído em `F5-02`.

## Decisão por item

| Item | Tipo | Estado | Decisão |
|---|---|---|---|
| `app/web_app.py` | Código legado | Não existe mais no repositório | Removido |
| `app/web_app_legacy.py` | Código legado | Não existe mais no repositório | Removido |
| Dependências `panel`, `plotly`, `bokeh` no backend | Dependência legada | Não aparecem mais em `pyproject.toml` | Removido |
| Docstrings/comentários citando `web_app.py` ou Panel | Resíduo técnico | Ainda apareciam em módulos Python | Remover quando enganosos |
| `doc/fase0_plan.md` com menções ao cutover Panel | Documento histórico | Mantido | Manter como registro de transição |
| `doc/backlog.md` com referências a F5-02 / Dashboard Panel | Documento de rastreabilidade | Mantido | Manter como histórico de planejamento |

## Resultado

- Não há superfície legada ativa de Panel no código executável atual.
- O legado restante é apenas histórico/documental.
- Referências técnicas enganosas devem ser limpas quando encontradas para não
  sugerirem que ainda existe um app `web_app.py` em produção.
