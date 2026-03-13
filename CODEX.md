## CODEX.md — Guia de agente para `ranking_msc`

> Este arquivo é o **guia permanente para agentes de IA** (Cursor/Codex) que atuam neste repositório.  
> Leia-o inteiro antes de implementar qualquer task ou modificar o código.

---

## 1. Papel deste guia

- **Para agentes de IA**: concentrar todas as regras de desenvolvimento, padrões de código e decisões técnicas que devem ser seguidas ao gerar ou editar código neste projeto.
- **Para pessoas desenvolvedoras**: servir como visão rápida de como o agente deve se comportar, em complemento ao `CLAUDE.md`.

Agentes devem sempre:

- Respeitar as convenções de código e padrões descritos aqui e em `CLAUDE.md`.
- Priorizar clareza, consistência e segurança (sem dados sensíveis, sem caminhos hardcodados).
- Manter compatibilidade com o pipeline e a arquitetura descritos na documentação do projeto.

---

## 2. Visão geral do projeto

Esta seção deve resumir, em alto nível, o que é o `ranking_msc`, como o pipeline funciona e em que fase o projeto está, tomando como base a seção "O que é este projeto" do `CLAUDE.md`.

---

## 3. Estrutura do repositório

Esta seção deve refletir a árvore de diretórios principal do projeto (como em `CLAUDE.md`), com foco em:

- Onde ficam os módulos principais (`engine`, `rules`, `io`, `transform`, `outputs`).
- Onde ficam os testes.
- Onde ficam arquivos de configuração, referências e dados gerados.

O objetivo é orientar o agente sobre **onde colocar novos arquivos** e **onde localizar código existente**.

---

## 4. Convenções de código para o agente

Esta seção deve consolidar as convenções de código descritas em `CLAUDE.md`, explicitando como o agente deve aplicá‑las:

- **Linguagem e nomes** (inglês para código, português para conceitos de negócio).
- **Estilo** (Python 3.11+, type hints em tudo, `from __future__ import annotations`, PEP8, imports agrupados).
- **Dataclasses** para qualquer estrutura de dados.
- **Exceções** sempre vindas de `ranking_msc.exceptions`, nunca `Exception` genérico.
- **Logging** via `logging.getLogger("ranking_msc")`, nunca `print()`.
- **Docstrings** em português para funções, classes e módulos públicos.

Cada subtópico pode citar exemplos curtos quando necessário.

---

## 5. Padrões de implementação assistida por agente

Esta seção deve adaptar os "Padrões de implementação" do `CLAUDE.md` para o contexto de agentes, incluindo:

- **Como implementar uma nova regra** (`rules/r<NNN>.py`, registro, habilitação em `settings.yaml`, testes).
- **Como adicionar uma nova coluna ao schema** (`schemas.py`, `reader_msc.py`, testes e docs de layout).
- **Como adicionar um novo módulo** dentro de subpacotes existentes.
- **Como ler tabelas de referência** usando `io/ref_loader.py`.

O foco aqui é orientar o agente em **fluxos passo a passo** para tarefas típicas.

---

## 6. Testes, lint e tipos

Esta seção deve orientar o agente sobre:

- Estrutura de testes (`tests/`, um arquivo por módulo, fixtures em `conftest.py`).
- Nomenclatura e estilo de testes (`pytest`).
- Uso de ferramentas de qualidade: `pytest`, `ruff`, `mypy`.

Sempre que possível, o agente deve:

- Criar ou atualizar testes ao modificar código.
- Evitar introduzir novos erros de lint ou tipos.

---

## 7. Fluxo de trabalho com Git (para agentes)

Com base na seção de Git do `CLAUDE.md`, esta seção deve esclarecer:

- Padrão de branches (`main`, `feat/F2-XX-descricao`).
- Formato de mensagens de commit.
- Expectativa de rodar testes e lints antes de commitar.

Agentes normalmente **não** devem criar commits ou branches sem pedido explícito, mas devem respeitar esses padrões quando forem instruídos a usar Git.

---

## 8. Decisões técnicas a respeitar

Esta seção deve resumir as decisões técnicas já tomadas (layout `src/`, uso de `dataclasses`, YAML + dataclasses `frozen` para config, Parquet para snapshots, Excel para relatórios, etc.) e como isso impacta o comportamento do agente:

- Não introduzir frameworks novos sem necessidade.
- Não alterar tecnologias já consolidadas sem justificativa forte.

---

## 9. Restrições e "não fazer"

Esta seção deve espelhar a lista de "O que NÃO fazer" do `CLAUDE.md`, com foco em:

- Proibições explícitas (`print()`, `raise Exception()`, hardcode de caminhos, etc.).
- Restrições de escopo (não alterar `app/web_app.py` na Fase 2).

Agentes devem checar esta lista antes de propor mudanças estruturais.

---

## 10. Checklist para o agente antes de concluir uma task

Inspirado na checklist do `CLAUDE.md`, esta seção deve listar, de forma adaptada para o uso por agentes:

- Convenções de código respeitadas.
- Exceções corretas.
- Logging adequado.
- Uso correto de schemas e `settings.paths`.
- Testes criados/atualizados quando necessário.
- Ferramentas de qualidade consideradas (mesmo que não sejam executadas diretamente pelo agente).

Esta checklist serve como referência final para o agente validar sua própria resposta antes de encerrar uma task.