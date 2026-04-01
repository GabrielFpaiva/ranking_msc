# Prompt — Arquitetura de Task (antes de implementar)

> Copie este prompt, substitua os placeholders e cole no Claude Code
> antes de iniciar qualquer task nova. Só implemente após aprovação do plano.

---

```
Leia primeiro o `claude.md` e siga rigorosamente os padrões do projeto.

Quero que você apenas ARQUITETE a task abaixo, sem implementar nada por enquanto.

Regras:
- Leia sempre o `claude.md` antes de decidir qualquer coisa.
- Crie uma NOVA BRANCH específica para esta task antes de qualquer alteração, usando o padrão:
  `feat/F<N>-<XX>-descricao-curta-kebab-case`
  Ajuste o nome conforme a task atual, mantendo prefixo, código da task e descrição curta em kebab-case.
- Sugira também a mensagem de commit inicial no padrão:
  `F<N>-XX: descrição curta em inglês`
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
5. Arquivos impactados
6. Passo a passo
7. Validações e riscos
8. Como garantir o critério de aceite
9. Plano final para aprovação

Task:
F3-02 — Implementar R011 e R012 (PCASP: nível e status da conta)

Contexto:
- R011 (ERRO): toda conta_contabil na MSC deve ser de último nível (analítica).
  Contas sintéticas (nivel == "Superior" no PCASP) não devem ser informadas.
- R012 (ALERTA): contas com status != "Ativa" no PCASP não devem constar no MSC.
  Indica possível uso de plano de contas desatualizado.
- Ambas dependem de R010 (conta existe no PCASP) já implementada.
- Tabela de referência: ref/pcasp.csv (sep=";") — colunas: conta_contabil, id_ic,
  nat_saldo, status, nivel, ind_sf
- load_pcasp() já existe em io/ref_loader.py e faz cache. Deve ser reutilizada.

Entregáveis:
- src/ranking_msc/rules/r011.py
- src/ranking_msc/rules/r012.py
- Registro em src/ranking_msc/rules/__init__.py
- Habilitação em config/settings.yaml.example
- Testes em tests/test_rules.py (ou arquivo próprio)

Critério de aceite:
- Conta com nivel == "Superior" no PCASP → R011 gera pendência com severidade ERRO.
- Conta com nivel == "Último" no PCASP → R011 não gera pendência.
- Conta com status != "Ativa" no PCASP → R012 gera pendência com severidade ALERTA.
- Conta com status == "Ativa" no PCASP → R012 não gera pendência.
- pytest passa sem erros.
- ruff check src/ tests/ sem erros.
- mypy src/ sem erros.
```

---

