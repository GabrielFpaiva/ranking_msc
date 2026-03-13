Leia primeiro o claude.md e siga rigorosamente os padrões do projeto.

Quero que você apenas ARQUITETE a task abaixo, sem implementar nada por enquanto.

Regras:
- Leia sempre o claude.md antes de decidir qualquer coisa.
- Crie uma NOVA BRANCH específica para esta task antes de qualquer alteração, usando o padrão:
  feat/F3-03-read-msc-csv-completo-pivot-testes
  Ajuste o nome conforme a task atual, mantendo prefixo, código da task e descrição curta em kebab-case.
- Sugira também a mensagem de commit inicial no padrão:
  F3-03: implementar read_msc_csv() completo com pivot e testes
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
[Criar script CLI de execução (run_pipeline.py)	]

Descrição task:
[Script que orquestra o pipeline completo via linha de comando: recebe caminho do CSV como argumento, carrega settings, lê CSV, normaliza IC, roda engine, grava snapshot, gera Excel, registra log. Serve como validação e também como alternativa ao web_app. Usar argparse com --csv, --config (opcional), --output-dir (opcional).	]

Entregável:
[scripts/run_pipeline.py executável	]
Referências: 
[]
Critério de aceite:
[python scripts/run_pipeline.py --csv ref/amostras/MSC_xxx.csv gera snapshot + Excel + log sem erro	]
