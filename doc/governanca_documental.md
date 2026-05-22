# Governança Documental e Aderência Arquitetural

> Status: ativo  
> Atualizado em: 2026-05-22  
> Issue de origem: #87

## 1. Fontes vivas oficiais

| Documento | Papel | Status |
|---|---|---|
| `README.md` | visão geral do produto, setup, comandos e superfície pública da API | **ativo** |
| `CLAUDE.md` | contexto operacional permanente e convenções de implementação | **ativo** |
| `doc/backlog.md` | status consolidado, roadmap executável e prioridades | **ativo** |
| `doc/modelo_pontuacao.md` | regra de negócio do score | **ativo** |
| `doc/governanca_documental.md` | política documental e revisão arquitetural | **ativo** |
| `doc/fase0_plan.md` | registro histórico da entrega de bootstrap/frontend | **histórico** |
| `doc/legacy_inventory.md` | registro histórico da limpeza de legado Panel | **histórico** |

## 2. Política documental

### 2.1 Quando criar documento novo

Criar documento novo só quando pelo menos uma destas condições for verdadeira:

- o conteúdo não cabe naturalmente em `README.md`, `CLAUDE.md`, `doc/backlog.md` ou `doc/modelo_pontuacao.md`;
- a informação precisa continuar válida por mais de uma task ou sprint;
- o tema precisa de referência consultável própria para operação, arquitetura ou regra de negócio.

Se a informação for apenas status, plano curto ou decisão local de uma task, ela deve entrar no `doc/backlog.md` ou no PR, não em arquivo novo.

### 2.2 Classificação obrigatória

Todo documento de `doc/` deve ser classificado como um dos tipos abaixo:

- **ativo**: fonte viva de operação, produto, arquitetura ou negócio;
- **histórico**: registro de contexto passado mantido por rastreabilidade;
- **temporário**: material auxiliar com prazo explícito para remoção ou incorporação.

### 2.3 Regra para documentos temporários

Documento temporário deve declarar no topo:

- status `temporário`;
- data de criação;
- owner ou task de origem;
- gatilho de expiração.

Sem isso, o documento não deve existir no repositório.

### 2.4 Regra de expiração

Documento temporário deve ser removido ou incorporado a uma fonte viva quando ocorrer o primeiro destes eventos:

- merge da task/PR que o motivou;
- encerramento da fase correspondente;
- perda de utilidade operacional.

### 2.5 Regra de atualização acoplada ao código

Mudança de código deve atualizar documentação na mesma branch quando afetar:

- setup, execução ou dependências locais;
- contrato público da API;
- convenção operacional do time;
- status do backlog executável;
- fronteira arquitetural relevante.

## 3. Política de descontinuação

Documento ativo vira histórico quando deixa de ser fonte de decisão corrente, mas ainda preserva contexto útil.

Critérios para remoção completa:

- o conteúdo está totalmente absorvido por fonte viva oficial; e
- não há ganho real de rastreabilidade em mantê-lo separado.

## 4. Checklist de aderência arquitetural

Arquitetura alvo do projeto:

```text
io -> transform -> engine -> outputs -> api/web
```

Checklist aplicado em 2026-05-22:

| Item | Resultado | Observação |
|---|---|---|
| `io` concentra leitura de CSV e referências | OK | `reader_msc.py` e `ref_loader.py` seguem essa responsabilidade |
| `transform` atua sobre dados já lidos | OK | `ic_normalize.py` permanece focado na normalização IC/TIPO |
| `engine` concentra regras e score | OK com ressalva | núcleo de execução está coeso; ver desvio D1 |
| `outputs` concentra snapshots, relatórios e agregações derivadas | OK | leitura/escrita persistida e agregações estão concentradas |
| `api/web` ficam na borda do sistema | OK com exceção aceita | API orquestra pipeline e expõe contratos; ver desvio D2 |

## 5. Desvios reais encontrados

### D1 — `engine.compare_periods` depende de `outputs.snapshot`

Evidência:

- `src/ranking_msc/engine/compare_periods.py` importa `read_snapshot` e `read_scoring_metadata` de `ranking_msc.outputs.snapshot`.

Impacto:

- a camada `engine` passa a conhecer detalhes de persistência/leitura histórica;
- a direção arquitetural deixa de ser estritamente monotônica.

Decisão:

- desvio registrado como relevante;
- issue aberta para refactor: **#98**.

### D2 — `app/api/routes/contas.py` lê PCASP diretamente em `io.ref_loader`

Evidência:

- a rota usa `load_pcasp()` para enriquecer o drawer de conta.

Impacto:

- a API acessa referência diretamente, sem passar por um adaptador em `outputs`.

Decisão:

- manter como exceção aceita por ora;
- não abrir issue agora, porque o acoplamento é local, explícito e de baixo risco.

## 6. Resultado da revisão

- Não há acúmulo relevante de documentação viva redundante.
- `doc/fase0_plan.md` e `doc/legacy_inventory.md` devem permanecer como documentos **históricos**, não como fontes correntes de decisão.
- A arquitetura principal segue reconhecível e operacional.
- O único desvio arquitetural considerado relevante nesta revisão já foi transformado em issue rastreável (#98).
