# Graph Report - .  (2026-04-13)

## Corpus Check
- Large corpus: 122 files · ~1,124,249 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 1701 nodes · 4576 edges · 31 communities detected
- Extraction: 44% EXTRACTED · 56% INFERRED · 0% AMBIGUOUS · INFERRED: 2545 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Exceptions & Infrastructure|Exceptions & Infrastructure]]
- [[_COMMUNITY_Rule Base & Registry|Rule Base & Registry]]
- [[_COMMUNITY_Test Fixtures & Helpers|Test Fixtures & Helpers]]
- [[_COMMUNITY_Rules Catalogue|Rules Catalogue]]
- [[_COMMUNITY_IC Normalization|IC Normalization]]
- [[_COMMUNITY_Balance & Result Rules|Balance & Result Rules]]
- [[_COMMUNITY_Temporal Rules & Snapshots|Temporal Rules & Snapshots]]
- [[_COMMUNITY_Logging & Audit|Logging & Audit]]
- [[_COMMUNITY_IC Domain — DC|IC Domain — DC]]
- [[_COMMUNITY_IC Domain — FR|IC Domain — FR]]
- [[_COMMUNITY_IC Format Validation|IC Format Validation]]
- [[_COMMUNITY_IC Set Validation|IC Set Validation]]
- [[_COMMUNITY_IC Domain — FP|IC Domain — FP]]
- [[_COMMUNITY_Closing Balance Rule (SF=SI+Mov)|Closing Balance Rule (SF=SI+Mov)]]
- [[_COMMUNITY_IC Domain — CO|IC Domain — CO]]
- [[_COMMUNITY_IC Domain — ND|IC Domain — ND]]
- [[_COMMUNITY_IC Domain — FS|IC Domain — FS]]
- [[_COMMUNITY_PCASP Cross-Validation|PCASP Cross-Validation]]
- [[_COMMUNITY_IC Domain — NR|IC Domain — NR]]
- [[_COMMUNITY_IC Domain — AI|IC Domain — AI]]
- [[_COMMUNITY_IC×TIPO Mapping|IC×TIPO Mapping]]
- [[_COMMUNITY_IC Domain — PO|IC Domain — PO]]
- [[_COMMUNITY_D=C Closing Tests|D=C Closing Tests]]
- [[_COMMUNITY_PCASP Existence Tests|PCASP Existence Tests]]
- [[_COMMUNITY_Report Generation|Report Generation]]
- [[_COMMUNITY_Column Schemas|Column Schemas]]
- [[_COMMUNITY_Module Init|Module Init]]
- [[_COMMUNITY_Module Init|Module Init]]
- [[_COMMUNITY_Module Init|Module Init]]
- [[_COMMUNITY_Module Init|Module Init]]
- [[_COMMUNITY_Module Init|Module Init]]

## God Nodes (most connected - your core abstractions)
1. `EngineContext` - 467 edges
2. `Settings` - 182 edges
3. `Rule` - 175 edges
4. `ConfigError` - 146 edges
5. `InputFormatError` - 99 edges
6. `R003` - 76 edges
7. `R004` - 76 edges
8. `RawMSC` - 71 edges
9. `R021` - 69 edges
10. `R030` - 69 edges

## Surprising Connections (you probably didn't know these)
- `Caminhos de diretórios do projeto.` --uses--> `ConfigError`  [INFERRED]
  src\ranking_msc\config\settings.py → src\ranking_msc\exceptions.py
- `Cria diretórios se não existirem.` --uses--> `ConfigError`  [INFERRED]
  src\ranking_msc\config\settings.py → src\ranking_msc\exceptions.py
- `Configuração das regras de validação.` --uses--> `ConfigError`  [INFERRED]
  src\ranking_msc\config\settings.py → src\ranking_msc\exceptions.py
- `Configuração consolidada do projeto.` --uses--> `ConfigError`  [INFERRED]
  src\ranking_msc\config\settings.py → src\ranking_msc\exceptions.py
- `Testes da regra R010 — Conta existe no PCASP Estendido 2026.` --uses--> `R010`  [INFERRED]
  tests\test_r010.py → src\ranking_msc\rules\r010.py

## Communities

### Community 0 - "Exceptions & Infrastructure"
Cohesion: 0.01
Nodes (232): Exception, ConcurrencyError, ConfigError, RankingMSCError, ranking_msc.exceptions ~~~~~~~~~~~~~~~~~~~~~~  Exceções customizadas do proje, Classe-base de todas as exceções do ranking_msc., Erro de configuração (YAML ausente, valor inválido, etc.)., Falha ao gravar ou ler snapshot Parquet de uma competência. (+224 more)

### Community 1 - "Rule Base & Registry"
Cohesion: 0.02
Nodes (159): ABC, ic_esta_informada(), ranking_msc.rules.base ~~~~~~~~~~~~~~~~~~~~~~  Interface base para todas as r, Retorna True se o valor de uma IC está preenchido (não é vazio).      Trata No, Decorator para registrar uma regra automaticamente.      Uso:         @regist, Classe-base abstrata para regras de validação.      Atributos de classe obriga, Executa a regra sobre o DataFrame MSC normalizado.          Args:, Constrói DataFrame de pendências com schema padronizado.          Preenche aut (+151 more)

### Community 2 - "Test Fixtures & Helpers"
Cohesion: 0.02
Nodes (147): build_msc_csv(), _build_msc_csv_bytes(), engine_context(), msc_csv_bytes(), msc_csv_bytesio(), msc_csv_path(), tests/conftest.py ~~~~~~~~~~~~~~~~~  Fixtures compartilhadas entre todos os m, Retorna a função _build_msc_csv_bytes para uso em testes. (+139 more)

### Community 3 - "Rules Catalogue"
Cohesion: 0.08
Nodes (85): ranking_msc.rules ~~~~~~~~~~~~~~~~~  Submódulo de regras de validação.  Cad, R001, R002, R003, R004, R005, R010, R011 (+77 more)

### Community 4 - "IC Normalization"
Cohesion: 0.03
Nodes (95): InputFormatError, CSV MSC com formato inválido ou colunas faltando., _find_unknown_combinations(), _format_combination(), _load_known_combinations(), normalize_ic(), _normalize_text_columns(), ranking_msc.transform.ic_normalize ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~  Norma (+87 more)

### Community 5 - "Balance & Result Rules"
Cohesion: 0.08
Nodes (51): R040, Verifica que contas patrimoniais possuem saldo inicial informado., R041, Verifica que contas patrimoniais possuem saldo final informado., R042, Verifica que contas de resultado não possuem saldo (apenas movimentos)., R043, Detecta contas com todas as colunas de valor zeradas. (+43 more)

### Community 6 - "Temporal Rules & Snapshots"
Cohesion: 0.05
Nodes (59): Snapshot de competência não encontrado em disco., SnapshotNotFoundError, _aggregate(), _prev_competencia(), R054, Regra R054 — Saldo Inicial do mês N = Saldo Final do mês N-1.  Dimensão: Tempo, Retorna a competência do mês anterior no formato YYYY-MM.      Args:, Agrega DataFrame por combo conta+ICs, somando colunas de valor.      Args: (+51 more)

### Community 7 - "Logging & Audit"
Cohesion: 0.08
Nodes (25): JSONLineFormatter, log_execucao(), ranking_msc.outputs.logs ~~~~~~~~~~~~~~~~~~~~~~~~~  Configuração de logging e, Emite log estruturado de uma execução do motor.      Exemplo:         log_exe, Formatter que emite cada registro como uma linha JSON.      Captura dinamicame, Formata um LogRecord como linha JSON., Configura o logger raiz do projeto.      Deve ser chamado UMA VEZ no início da, setup_logging() (+17 more)

### Community 8 - "IC Domain — DC"
Cohesion: 0.1
Nodes (20): R023, Regra R023 — DC (Dívida Consolidada) válido.  Categoria: IC Severidade padrão, Valida se o valor de DC é "1" (não compõe Dívida Consolidada)., Verifica se os valores de DC estão no domínio permitido {"1"}.          Args:, _df_com_dc(), Testes da regra R023 — DC válido: domínio "1"., Mesma combinação conta+dc repetida → uma única pendência por par único., Contas com DC válido e inválido na mesma entrada → apenas as inválidas geram err (+12 more)

### Community 9 - "IC Domain — FR"
Cohesion: 0.1
Nodes (20): R024, Regra R024 — FR válido: 4 dígitos, prefixo {1, 2, 9} e código-raiz na tabela., Valida formato (4 dígitos), prefixo e código-raiz do campo FR., Verifica se os valores de FR são válidos em formato, prefixo e domínio., _df(), Testes para a regra R024 — FR válida — 4 dígitos + tabela., Mesma combinação conta/FR duplicada → apenas 1 pendência., Cria DataFrame mínimo para testes de R024. (+12 more)

### Community 10 - "IC Format Validation"
Cohesion: 0.11
Nodes (20): R081, Valida que cada IC informada tem o número correto de dígitos numéricos., _make_df(), tests/test_r081.py ~~~~~~~~~~~~~~~~~~  Testes para a regra R081 — IC tem dígi, ND com menos de 8 dígitos gera ERRO., Múltiplas ICs inválidas geram uma pendência cada., Coluna IC ausente no DataFrame não gera pendência (skip silencioso)., Pendência gerada deve conter a competência do contexto. (+12 more)

### Community 11 - "IC Set Validation"
Cohesion: 0.13
Nodes (20): R020, Valida se o conjunto de ICs informadas corresponde ao ID_IC da conta no PCASP., _df_com_ics(), _pcasp_stub(), Testes da regra R020 — Conjunto de IC correto para a conta., ID_IC=2 (PO+FP) → po informado mas co está extra → um único ERRO descrevendo amb, Gera um PCASP mínimo para testes.      Args:         contas: lista de tuplas, ID_IC=0 → nenhuma IC esperada e nenhuma informada → sem pendência. (+12 more)

### Community 12 - "IC Domain — FP"
Cohesion: 0.11
Nodes (19): R022, Valida se o valor de FP é "1" (Financeiro) ou "2" (Permanente)., _df_com_fp(), Testes da regra R022 — FP válido: domínio "1" ou "2"., DataFrame sem coluna fp → nenhuma pendência (regra inaplicável)., Mesma combinação conta+fp repetida → uma única pendência por par único., Contas com FP válido e inválido na mesma entrada → apenas as inválidas geram err, Cria DataFrame mínimo com uma conta e um valor de FP. (+11 more)

### Community 13 - "Closing Balance Rule (SF=SI+Mov)"
Cohesion: 0.1
Nodes (19): R031, Regra R031 — Saldo Final = Saldo Inicial + Movimentos.  Dimensão: Fechamento, Verifica que SF = SI + Movimentos para cada linha CONTA+ICs., Detecta combos CONTA+ICs onde o saldo final diverge de SI + movimentos., _df(), Testes da regra R031 — SF = SI + Movimentos., Apenas a conta com SF errado aparece nas pendências., DataFrame sem linhas retorna DataFrame de pendências vazio. (+11 more)

### Community 14 - "IC Domain — CO"
Cohesion: 0.11
Nodes (17): R025, Regra R025 — CO válido: 4 dígitos e existente na tabela CO.  Categoria: IC Se, Valida formato (4 dígitos) e existência do CO na tabela oficial., Verifica se os valores de CO são válidos em formato e domínio.          Para c, _df(), Testes para a regra R025 — CO válido — 4 dígitos + tabela., Cria DataFrame mínimo para testes de R025., CO existente na tabela → nenhuma pendência. (+9 more)

### Community 15 - "IC Domain — ND"
Cohesion: 0.11
Nodes (17): R027, Regra R027 — ND válida: 8 dígitos e existente na tabela ND.  Categoria: IC Se, Valida formato (8 dígitos) e existência do ND na tabela oficial., Verifica se os valores de ND são válidos em formato e domínio.          Para c, _df(), Testes para a regra R027 — ND válida — 8 dígitos + tabela., Cria DataFrame mínimo para testes de R027., ND existente na tabela → nenhuma pendência. (+9 more)

### Community 16 - "IC Domain — FS"
Cohesion: 0.11
Nodes (17): R028, Regra R028 — FS válida: 5 dígitos (2 função + 3 subfunção).  Categoria: IC Se, Valida formato (5 dígitos), função (2 dígitos) e subfunção (3 dígitos) do FS., Verifica se os valores de FS são válidos em formato, função e subfunção., _df(), Testes para a regra R028 — FS válida — 5 dígitos (2 função + 3 subfunção)., Cria DataFrame mínimo para testes de R028., FS com função e subfunção válidas → nenhuma pendência. (+9 more)

### Community 17 - "PCASP Cross-Validation"
Cohesion: 0.15
Nodes (18): R060, Verifica compatibilidade entre FP informado na MSC e IND_SF definido no PCASP., _msc(), _pcasp(), tests/test_r060.py — Testes para R060 (FP coerente com IND_SF PCASP)., ind_sf com espaços no PCASP deve ser normalizado — FP correto não gera ALERTA., Múltiplas contas com FP divergente → um ALERTA por conta., Constrói DataFrame PCASP de teste. (+10 more)

### Community 18 - "IC Domain — NR"
Cohesion: 0.12
Nodes (16): R026, Regra R026 — NR válida: 8 dígitos e existente na tabela NR.  Categoria: IC Se, Valida formato (8 dígitos) e existência do NR na tabela oficial., Verifica se os valores de NR são válidos em formato e domínio.          Para c, _df(), Testes para a regra R026 — NR válida — 8 dígitos + tabela., Cria DataFrame mínimo para testes de R026., NR existente na tabela → nenhuma pendência. (+8 more)

### Community 19 - "IC Domain — AI"
Cohesion: 0.12
Nodes (16): R029, Regra R029 — AI (Ano Inscrição RP) válido.  Categoria: IC Severidade: ERRO (f, Valida formato (4 dígitos) e plausibilidade do Ano Inscrição RP., Verifica formato e plausibilidade do campo ai.          Args:             df:, _df_ai(), Testes da regra R029 — AI: Ano Inscrição RP válido., DataFrame mínimo com uma linha e colunas conta_contabil + ai., Linha sem AI (coluna vazia) não gera pendência. (+8 more)

### Community 20 - "IC×TIPO Mapping"
Cohesion: 0.09
Nodes (15): combinacoes_mapeamento(), combinacoes_reais(), mapeamento_df(), Testes de cobertura do mapeamento IC × TIPO.  Valida que ref/mapeamento_ic_tip, Todos os valores de TIPO são válidos ou vazios., Carrega ref/mapeamento_ic_tipo.csv., Extrai todas as combinações únicas de TIPO dos CSVs reais., Extrai as combinações de TIPO do mapeamento. (+7 more)

### Community 21 - "IC Domain — PO"
Cohesion: 0.2
Nodes (10): _df_com_po(), Testes da regra R021 — PO válido: 5 dígitos e existente na tabela., Tabela PO reduzida para testes., PO com 5 dígitos e existente na tabela não gera pendência., Conta sem IC do tipo PO (po vazio) não gera pendência., PO com número de dígitos diferente de 5 gera pendência ERRO., PO com 5 dígitos mas ausente da tabela gera pendência ERRO., Contas distintas com PO inválido geram uma pendência cada. (+2 more)

### Community 22 - "D=C Closing Tests"
Cohesion: 0.15
Nodes (9): _df(), Testes da regra R030 — Débito = Crédito por conta (fechamento patrimonial)., Conta patrimonial com D=C exato não gera pendência., Diferença D-C dentro da tolerância de 0.01 não gera pendência., Conta patrimonial com D≠C gera pendência ERRO., Contas das classes 5-9 (resultado, controle) não são verificadas., Movimentos de múltiplas ICs são somados antes da comparação., Várias contas patrimoniais com D≠C geram uma pendência cada. (+1 more)

### Community 23 - "PCASP Existence Tests"
Cohesion: 0.21
Nodes (8): _pcasp_stub(), Testes da regra R010 — Conta existe no PCASP Estendido 2026., PCASP reduzido para testes., Conta existente no PCASP não gera pendência., Conta ausente no PCASP gera pendência ERRO., Cada conta inválida única gera uma pendência separada., Conta inválida repetida no DataFrame gera apenas uma pendência., TestR010

### Community 24 - "Report Generation"
Cohesion: 0.47
Nodes (5): add_heading(), build_doc(), Script temporário para gerar doc/relatorio_fase2.docx a partir do Markdown., Aplica fundo escuro e texto branco na linha de cabeçalho., shade_header_row()

### Community 25 - "Column Schemas"
Cohesion: 1.0
Nodes (1): ranking_msc.schemas ~~~~~~~~~~~~~~~~~~~  Constantes com as colunas esperadas

### Community 26 - "Module Init"
Cohesion: 1.0
Nodes (0): 

### Community 27 - "Module Init"
Cohesion: 1.0
Nodes (0): 

### Community 28 - "Module Init"
Cohesion: 1.0
Nodes (0): 

### Community 29 - "Module Init"
Cohesion: 1.0
Nodes (0): 

### Community 30 - "Module Init"
Cohesion: 1.0
Nodes (0): 

## Knowledge Gaps
- **31 isolated node(s):** `# TODO: adicionar gráficos Plotly (gauge do score, barras por severidade)`, `Script temporário para gerar doc/relatorio_fase2.docx a partir do Markdown.`, `Aplica fundo escuro e texto branco na linha de cabeçalho.`, `ranking_msc.exceptions ~~~~~~~~~~~~~~~~~~~~~~  Exceções customizadas do proje`, `Classe-base de todas as exceções do ranking_msc.` (+26 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Column Schemas`** (2 nodes): `ranking_msc.schemas ~~~~~~~~~~~~~~~~~~~  Constantes com as colunas esperadas`, `schemas.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `EngineContext` connect `Rule Base & Registry` to `Exceptions & Infrastructure`, `Test Fixtures & Helpers`, `Rules Catalogue`, `Balance & Result Rules`, `Temporal Rules & Snapshots`, `IC Domain — DC`, `IC Domain — FR`, `IC Format Validation`, `IC Set Validation`, `IC Domain — FP`, `Closing Balance Rule (SF=SI+Mov)`, `IC Domain — CO`, `IC Domain — ND`, `IC Domain — FS`, `PCASP Cross-Validation`, `IC Domain — NR`, `IC Domain — AI`?**
  _High betweenness centrality (0.563) - this node is a cross-community bridge._
- **Why does `ConfigError` connect `Exceptions & Infrastructure` to `Rule Base & Registry`, `Test Fixtures & Helpers`, `IC Normalization`, `Temporal Rules & Snapshots`?**
  _High betweenness centrality (0.184) - this node is a cross-community bridge._
- **Why does `Rule` connect `Rule Base & Registry` to `Exceptions & Infrastructure`, `Test Fixtures & Helpers`, `Rules Catalogue`, `Balance & Result Rules`, `Temporal Rules & Snapshots`, `IC Domain — DC`, `IC Domain — FR`, `IC Format Validation`, `IC Set Validation`, `IC Domain — FP`, `Closing Balance Rule (SF=SI+Mov)`, `IC Domain — CO`, `IC Domain — ND`, `IC Domain — FS`, `PCASP Cross-Validation`, `IC Domain — NR`, `IC Domain — AI`?**
  _High betweenness centrality (0.122) - this node is a cross-community bridge._
- **Are the 465 inferred relationships involving `EngineContext` (e.g. with `OutputPaths` and `Diretórios de saída usados pela execução CLI.`) actually correct?**
  _`EngineContext` has 465 INFERRED edges - model-reasoned connections that need verification._
- **Are the 179 inferred relationships involving `Settings` (e.g. with `app/web_app.py ~~~~~~~~~~~~~~  Aplicação web Panel — interface principal do R` and `Callback do botão Processar.      Fluxo futuro:         1. Validar que um arq`) actually correct?**
  _`Settings` has 179 INFERRED edges - model-reasoned connections that need verification._
- **Are the 170 inferred relationships involving `Rule` (e.g. with `EngineContext` and `R001`) actually correct?**
  _`Rule` has 170 INFERRED edges - model-reasoned connections that need verification._
- **Are the 143 inferred relationships involving `ConfigError` (e.g. with `AppSettings` and `PathsSettings`) actually correct?**
  _`ConfigError` has 143 INFERRED edges - model-reasoned connections that need verification._