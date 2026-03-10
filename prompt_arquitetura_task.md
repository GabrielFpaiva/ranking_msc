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
[COLE A TASK AQUI]

Critério de aceite:
[COLE O CRITÉRIO DE ACEITE AQUI]
```

---

