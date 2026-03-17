# Catálogo de Regras de Validação MSC — Motor ranking_msc

> **Fonte:** Leiaute MSC 2026 (Anexo II, Portaria STN 642), Regras Gerais MSC 2026 (Anexo I),
> Documento de Validações de Consistência da MSC (Siconfi), MCASP, MDF.
>
> **Total: 67 regras** — 32 ERRO · 26 ALERTA · 6 INFO
>
> **Versão:** 2026-03-17

---

## Índice de Categorias

| Categoria | Regras | ERRO | ALERTA | INFO | Tabela Referência |
|---|---|---|---|---|---|
| Estrutura | R001–R009, R0010–R0011 | 10 | 0 | 0 | Observações Leiaute |
| PCASP | R010–R012 | 1 | 1 | 0 | PcaspEstendido2026 |
| IC | R020, R033–R034, R038, R082 | 4 | 1 | 0 | Leiaute MSC + Conjunto de IC |
| PO | R021, R039 | 1 | 1 | 0 | Aba PO (92 códigos) |
| FP | R022 | 1 | 0 | 0 | — (domínio fixo: 1 ou 2) |
| DC | R023, R063 | 2 | 0 | 0 | Leiaute MSC (105 contas ID_IC=8) |
| FR | R024, R048 | 1 | 1 | 0 | Aba FR 2026 (194 códigos-raiz) |
| CO | R025, R064 | 1 | 1 | 0 | Aba CO 2026 (50 códigos) |
| NR | R026, R044 | 1 | 1 | 0 | Aba NR 2026 (4504 valorizáveis) |
| ND | R027, R045–R047 | 1 | 3 | 0 | Aba ND 2026 (1072 último nível) |
| FS | R028, R065 | 1 | 0 | 1 | Aba FS (Portaria MOG 42/99) |
| AI | R029 | 0 | 1 | 0 | — |
| Fechamento | R030–R032, R035–R037 | 4 | 2 | 0 | PCASP (NAT_SALDO) |
| Interconta | R050–R053 | 1 | 3 | 0 | — |
| Superávit | R060–R062 | 0 | 3 | 0 | PCASP (IND_SF) |
| Completude | R040–R043, R066–R068, R074 | 0 | 6 | 2 | — |
| Temporal | R054–R055, R069 | 0 | 3 | 0 | — |
| Duplicidade | R070 | 1 | 0 | 0 | — |
| Formato | R080–R081 | 2 | 0 | 0 | Informações Complementares |
| Qualidade | R071–R073 | 0 | 0 | 3 | — |

---

## Legenda

- **Severidade ERRO:** Bloqueador. O Siconfi rejeitaria o arquivo ou o dado é objetivamente inválido.
- **Severidade ALERTA:** Impacta o score ICF. Inconsistência provável que precisa atenção.
- **Severidade INFO:** Heurística de qualidade. Não é erro, mas merece revisão humana.
- **Prioridade P0 (Blocker):** Implementar primeiro — sem isso o pipeline não funciona.
- **Prioridade P1 (Crítica):** Core do motor de regras.
- **Prioridade P2 (Alta):** Importante para score realista.
- **Prioridade P3 (Média):** Nice-to-have, melhora a cobertura.

---

## Tabelas de Referência Necessárias

O `ref_loader` deve expor estas tabelas (carregadas do xlsx STN 2026):

| Tabela | Fonte (aba xlsx) | Chave | Registros | Usado por |
|---|---|---|---|---|
| `pcasp` | PcaspEstendido2026 | CONTA (9 dig) | 6119 (último+ativa) | R010–R012, R020, R031–R032, R060–R062 |
| `leiaute_msc` | Leiaute MSC | CONTA → TIPOs | 6119 linhas | R020, R038 |
| `tabela_po` | PO | Código (5 dig) | 92 | R021, R039 |
| `tabela_fr` | FR 2026 | Código (3 dig raiz) | 194 | R024, R048 |
| `tabela_co` | CO 2026 | Código (4 dig) | 50 | R025, R064 |
| `tabela_nr` | NR 2026 | NR (8 dig) | 5450 (4504 valorizáveis) | R026, R044 |
| `tabela_nd` | ND 2026 | Codigo (8 dig) | 1235 (1072 último) | R027, R045–R047 |
| `tabela_fs` | FS | Função (2d) + Subfunção (3d) | ~120 | R028, R065 |
| `ic_map` | Conjunto de IC | ID_IC → lista de tipos | 9 entradas | R020, R038 |

O `ic_map` deve ser um dict:
```python
IC_MAP: dict[int, list[str]] = {
    0: [],
    1: ["PO"],
    2: ["PO", "FP"],
    3: ["PO", "FP", "DC"],
    4: ["PO", "FP", "FR", "CO"],
    5: ["PO", "FR", "CO"],
    6: ["PO", "FR", "CO", "NR"],
    7: ["PO", "FS", "FR", "CO", "ND"],
    8: ["PO", "FP", "DC", "FR"],
    9: ["PO", "FS", "FR", "CO", "ND", "AI"],
}
```

O mapa de dígitos esperados por tipo de IC:
```python
IC_DIGITOS: dict[str, int] = {
    "PO": 5, "FP": 1, "DC": 1, "FR": 4,
    "CO": 4, "NR": 8, "ND": 8, "FS": 5, "AI": 4,
}
```

---

## Regras — Especificação Completa

### CATEGORIA: Estrutura

#### R001 — Colunas obrigatórias presentes
- **Severidade:** ERRO | **Prioridade:** P0
- **Lógica:** Verifica se o CSV MSC contém todas as colunas obrigatórias do leiaute: CONTA, IC1–IC6, TIPO1–TIPO6, Valor, Tipo_valor, Natureza_valor.
- **Pseudocódigo:**
  ```
  colunas_obrigatorias = {"CONTA","IC1","TIPO1","IC2","TIPO2","IC3","TIPO3",
                          "IC4","TIPO4","IC5","TIPO5","IC6","TIPO6",
                          "Valor","Tipo_valor","Natureza_valor"}
  SE colunas_arquivo ⊅ colunas_obrigatorias → ERRO(colunas_faltantes)
  ```
- **Entrada:** Header do CSV
- **OK:** Todas colunas presentes
- **ERRO:** Lista de colunas faltantes
- **Tabela:** Leiaute MSC (cabeçalho)
- **Depende:** —

#### R002 — Linhas sem CONTA vazia
- **Severidade:** ERRO | **Prioridade:** P0
- **Lógica:** Toda linha de dados deve ter o campo CONTA preenchido. Linhas sem CONTA são inválidas.
- **Pseudocódigo:**
  ```
  PARA CADA linha:
    SE CONTA é vazio/nulo → ERRO(linha_idx)
  ```
- **Entrada:** Coluna CONTA
- **Depende:** R001

#### R003 — Tipo_valor válido
- **Severidade:** ERRO | **Prioridade:** P0
- **Lógica:** O campo Tipo_valor deve ser um dos 3 valores padronizados: beginning_balance, ending_balance, period_change.
- **Pseudocódigo:**
  ```
  valores_validos = {"beginning_balance", "ending_balance", "period_change"}
  SE Tipo_valor NOT IN valores_validos → ERRO(linha, valor_encontrado)
  ```
- **Entrada:** Coluna Tipo_valor
- **Depende:** R001

#### R004 — Natureza_valor válida
- **Severidade:** ERRO | **Prioridade:** P0
- **Lógica:** O campo Natureza_valor deve ser D (devedor) ou C (credor).
- **Pseudocódigo:**
  ```
  SE Natureza_valor NOT IN {"D", "C"} → ERRO(linha, valor_encontrado)
  ```
- **Entrada:** Coluna Natureza_valor
- **Depende:** R001

#### R005 — Valor numérico válido
- **Severidade:** ERRO | **Prioridade:** P0
- **Lógica:** O campo Valor deve ser numérico, sem separadores de milhares, usando ponto como separador decimal. Escala R$ 1,00.
- **Pseudocódigo:**
  ```
  PARA CADA linha:
    TRY: float(Valor)
    EXCEPT: ERRO(linha, valor_original)
    SE contém "," ou caractere não numérico (exceto ".") → ERRO
  ```
- **Entrada:** Coluna Valor
- **Depende:** R001

#### R006 — Código Siconfi válido (1a linha)
- **Severidade:** ERRO | **Prioridade:** P0
- **Lógica:** A primeira linha do CSV deve conter o código da instituição Siconfi (código IBGE + "EX") e o período no formato YYYY-MM.
- **Pseudocódigo:**
  ```
  linha_1 = csv[0]
  SE NOT re.match(r"\d{7}EX", cod_siconfi) → ERRO("código Siconfi inválido")
  SE NOT re.match(r"\d{4}-\d{2}", periodo) → ERRO("período inválido")
  ```
- **Entrada:** Primeira linha do CSV
- **Fonte:** Doc. Validações MSC Siconfi (item a)
- **Depende:** —

#### R007 — Período YYYY-MM válido e plausível
- **Severidade:** ERRO | **Prioridade:** P0
- **Lógica:** O mês deve estar entre 01-13 (13=encerramento) e o ano deve ser plausível.
- **Pseudocódigo:**
  ```
  ano, mes = periodo.split("-")
  SE int(mes) < 1 OR int(mes) > 13 → ERRO
  SE int(ano) < 2020 OR int(ano) > ano_corrente + 1 → ERRO
  ```
- **Entrada:** Período na primeira linha
- **Fonte:** Doc. Validações MSC Siconfi (item b)
- **Depende:** —

#### R008 — Separador ponto-e-vírgula no CSV
- **Severidade:** ERRO | **Prioridade:** P0
- **Lógica:** Campos do CSV devem ser separados por ponto-e-vírgula (;), não vírgula. Padrão oficial do Siconfi.
- **Pseudocódigo:**
  ```
  SE delimitador_detectado != ";" → ERRO("separador incorreto")
  ```
- **Entrada:** Arquivo CSV bruto
- **Fonte:** Doc. Validações MSC (item e)
- **Depende:** —

#### R009 — Exatamente 6 conjuntos de IC (12 colunas IC/TIPO)
- **Severidade:** ERRO | **Prioridade:** P0
- **Lógica:** O CSV deve ter exatamente 6 pares IC/TIPO (12 colunas de IC), totalizando 16 colunas.
- **Pseudocódigo:**
  ```
  colunas_ic = [c for c in colunas if c.startswith("IC") or c.startswith("TIPO")]
  SE len(colunas_ic) != 12 → ERRO(f"esperado 12, encontrado {len}")
  ```
- **Entrada:** Header do CSV
- **Fonte:** Doc. Validações MSC (item c)
- **Depende:** R001

#### R0010 — Cabeçalho (linha-guia) no padrão oficial
- **Severidade:** ERRO | **Prioridade:** P0
- **Lógica:** A segunda linha do CSV deve ser a linha-guia com os nomes exatos das colunas.
- **Pseudocódigo:**
  ```
  cabecalho_esperado = ["CONTA","IC1","TIPO1",...,"Valor","Tipo_valor","Natureza_valor"]
  SE cabecalho_csv != cabecalho_esperado → ERRO(diferenças)
  ```
- **Entrada:** Linha 2 do CSV
- **Fonte:** Doc. Validações MSC (item d)
- **Depende:** R001

#### R0011 — Valores não-negativos
- **Severidade:** ERRO | **Prioridade:** P1
- **Lógica:** O Siconfi não permite carregamento de valores negativos. Todos valores na coluna Valor devem ser >= 0.
- **Pseudocódigo:**
  ```
  PARA CADA linha:
    SE float(Valor) < 0 → ERRO("valor negativo", linha, valor)
  ```
- **Entrada:** Coluna Valor
- **Fonte:** Doc. Regras Gerais MSC 2026
- **Depende:** R005

---

### CATEGORIA: PCASP

#### R010 — Conta existe no PCASP Estendido 2026
- **Severidade:** ERRO | **Prioridade:** P1
- **Lógica:** Toda CONTA informada deve existir na tabela PcaspEstendido2026. Contas inexistentes indicam erro de digitação ou versão desatualizada.
- **Pseudocódigo:**
  ```
  pcasp = ref_loader.load_pcasp()
  SE CONTA NOT IN pcasp.CONTA → ERRO(conta_invalida)
  ```
- **Entrada:** Coluna CONTA
- **Tabela:** PcaspEstendido2026 (6119 contas ativas, último nível)
- **Depende:** R001

#### R011 — Conta é de último nível
- **Severidade:** ERRO | **Prioridade:** P1
- **Lógica:** O MSC deve conter apenas contas de último nível (analíticas). Contas sintéticas (Superior) não devem ser informadas.
- **Pseudocódigo:**
  ```
  SE pcasp[CONTA].NIVEL != "Último" → ERRO("conta sintética", conta)
  ```
- **Entrada:** Coluna CONTA + PCASP.NIVEL
- **Depende:** R010

#### R012 — Conta está Ativa
- **Severidade:** ALERTA | **Prioridade:** P1
- **Lógica:** Contas com STATUS != Ativa no PCASP não devem constar no MSC.
- **Pseudocódigo:**
  ```
  SE pcasp[CONTA].STATUS != "Ativa" → ALERTA(conta_inativa)
  ```
- **Entrada:** Coluna CONTA + PCASP.STATUS
- **Depende:** R010

---

### CATEGORIA: IC (Informações Complementares)

#### R020 — Conjunto de IC correto para a conta
- **Severidade:** ERRO | **Prioridade:** P1
- **Lógica:** Cada conta tem um ID_IC no PCASP que define QUAL conjunto de ICs é obrigatório. Ex: ID_IC=4 → PO,FP,FR,CO.
- **Pseudocódigo:**
  ```
  ic_esperado = IC_MAP[pcasp[CONTA].ID_IC]
  ic_informado = [TIPO_n para n em 1..6 se notna(TIPO_n)]
  SE set(ic_informado) != set(ic_esperado) → ERRO(conta, esperado, informado)
  ```
- **Entrada:** TIPO1–TIPO6 + PCASP.ID_IC
- **Tabela:** Conjunto de IC + PcaspEstendido2026
- **Depende:** R010

#### R033 — IC e TIPO sempre em pares
- **Severidade:** ERRO | **Prioridade:** P1
- **Lógica:** Para cada IC preenchida deve existir um TIPO correspondente e vice-versa. Regra oficial do Siconfi.
- **Pseudocódigo:**
  ```
  PARA n em 1..6:
    ic_preenchida = pd.notna(IC_n)
    tipo_preenchido = pd.notna(TIPO_n)
    SE ic_preenchida != tipo_preenchido → ERRO(f"IC{n}/TIPO{n} desemparelhados")
  ```
- **Entrada:** Colunas IC1–IC6 e TIPO1–TIPO6
- **Fonte:** Doc. Validações MSC (item j)
- **Depende:** R001

#### R034 — Todos registros devem ter PO preenchido
- **Severidade:** ERRO | **Prioridade:** P1
- **Lógica:** TODOS os registros da MSC devem possuir a IC de PO. O PO é obrigatório para 100% das contas.
- **Pseudocódigo:**
  ```
  PARA CADA linha:
    po_encontrado = ANY(TIPO_n == "PO" AND pd.notna(IC_n) for n in 1..6)
    SE NOT po_encontrado → ERRO("registro sem PO")
  ```
- **Entrada:** TIPO1–TIPO6 e IC1–IC6
- **Fonte:** Doc. Validações MSC (item d, conteúdo)
- **Depende:** R001

#### R038 — IC associada à conta correta (Conta×IC do leiaute)
- **Severidade:** ERRO | **Prioridade:** P1
- **Lógica:** As ICs informadas devem estar corretamente associadas às contas conforme o leiaute MSC. Conta 1.1.1.1 aceita PO,FP,FR,CO mas NÃO aceita NR ou ND.
- **Pseudocódigo:**
  ```
  leiaute = ref_loader.load_leiaute_msc()
  tipos_informados = {TIPO_n para n em 1..6 se notna}
  tipos_permitidos = leiaute[CONTA].tipos_validos
  SE tipos_informados ⊄ tipos_permitidos → ERRO(tipos_invalidos)
  ```
- **Entrada:** TIPO1–TIPO6 + Leiaute MSC
- **Fonte:** Doc. Validações MSC (item c, conteúdo)
- **Depende:** R010, R020

#### R082 — Ordem das ICs conforme padrão do leiaute
- **Severidade:** ALERTA | **Prioridade:** P3
- **Lógica:** O leiaute define uma ordem padrão para os tipos de IC: PO sempre em IC1/TIPO1, depois FP ou FS em IC2, etc. Manter o padrão facilita validação.
- **Pseudocódigo:**
  ```
  # Verificar se TIPO_n está na posição esperada conforme leiaute
  # PO→pos1, FP/FS→pos2, FR/DC→pos3, CO/FR→pos4, ND→pos5, AI→pos6
  ```
- **Entrada:** TIPO1–TIPO6
- **Depende:** R033

---

### CATEGORIA: PO (Poder/Órgão)

#### R021 — PO válido — 5 dígitos e existente na tabela
- **Severidade:** ERRO | **Prioridade:** P1
- **Lógica:** Quando a conta exige IC do tipo PO, o valor deve ter 5 dígitos e existir na tabela PO.
- **Pseudocódigo:**
  ```
  SE TIPO_n == "PO":
    SE len(IC_n) != 5 → ERRO("PO fora do formato")
    SE IC_n NOT IN tabela_PO → ERRO("PO inexistente")
  ```
- **Entrada:** IC onde TIPO=PO
- **Tabela:** Aba PO (92 códigos)
- **Depende:** R020

#### R039 — PO compatível com esfera do ente
- **Severidade:** ALERTA | **Prioridade:** P2
- **Lógica:** O PO informado deve ser compatível com a esfera do ente (Municipal/Estadual/Federal). Município não deve usar PO de Governo Federal (10101) ou Estadual (10111).
- **Pseudocódigo:**
  ```
  SE ente == "municipal":
    po_validos = {10131, 10132, 20231, 20232, ...}
    SE PO NOT IN po_validos → ALERTA("PO incompatível com esfera")
  ```
- **Entrada:** IC tipo PO + configuração do ente
- **Depende:** R021

---

### CATEGORIA: FP (Financeiro/Permanente)

#### R022 — FP válido — 1 dígito (1 ou 2)
- **Severidade:** ERRO | **Prioridade:** P1
- **Lógica:** O atributo do superávit financeiro deve ser 1 (Financeiro) ou 2 (Permanente).
- **Pseudocódigo:**
  ```
  SE TIPO_n == "FP":
    SE IC_n NOT IN {"1", "2"} → ERRO("FP inválido")
  ```
- **Entrada:** IC onde TIPO=FP
- **Depende:** R020

---

### CATEGORIA: DC (Dívida Consolidada)

#### R023 — DC válido — 1 dígito (valor 1)
- **Severidade:** ERRO | **Prioridade:** P2
- **Lógica:** O marcador de dívida consolidada deve ser 1 (não compõe DC).
- **Pseudocódigo:**
  ```
  SE TIPO_n == "DC":
    SE IC_n != "1" → ERRO("DC inválido")
  ```
- **Entrada:** IC onde TIPO=DC
- **Depende:** R020

#### R063 — DC só nas contas permitidas pelo leiaute
- **Severidade:** ERRO | **Prioridade:** P2
- **Lógica:** A IC de DC só deve aparecer nas contas que o leiaute define com ID_IC=8. São 105 contas de financiamentos.
- **Pseudocódigo:**
  ```
  contas_dc_permitidas = pcasp[pcasp.ID_IC == 8].CONTA
  SE TIPO == "DC" AND CONTA NOT IN contas_dc_permitidas → ERRO
  ```
- **Entrada:** TIPO="DC" + Leiaute MSC
- **Depende:** R020, R023

---

### CATEGORIA: FR (Fonte de Recursos)

#### R024 — FR válida — 4 dígitos + tabela
- **Severidade:** ERRO | **Prioridade:** P1
- **Lógica:** A fonte de recursos deve ter 4 dígitos. 1º dígito: 1=atual, 2=anterior, 9=condicionado. Dígitos 2-4 devem pertencer à tabela FR.
- **Pseudocódigo:**
  ```
  SE TIPO_n == "FR":
    SE len(IC_n) != 4 → ERRO("FR formato")
    SE IC_n[0] NOT IN {"1", "2", "9"} → ERRO("FR exercício")
    SE IC_n[1:] NOT IN tabela_FR → ALERTA("FR desconhecida")
  ```
- **Entrada:** IC onde TIPO=FR
- **Tabela:** Aba FR 2026 (194 códigos-raiz)
- **Depende:** R020

#### R048 — FR 1º dígito coerente com exercício
- **Severidade:** ALERTA | **Prioridade:** P2
- **Lógica:** O 1º dígito da FR indica exercício. Valor fora de {1, 2, 9} é inválido.
- **Pseudocódigo:**
  ```
  SE FR[0] NOT IN {"1", "2", "9"} → ERRO("primeiro dígito inválido")
  # FR começando com 2 é esperado em beginning_balance (saldos de exercício anterior)
  ```
- **Entrada:** IC tipo FR
- **Depende:** R024

---

### CATEGORIA: CO (Cód. Acompanhamento Exec. Orçamentária)

#### R025 — CO válido — 4 dígitos + tabela
- **Severidade:** ERRO | **Prioridade:** P2
- **Lógica:** O código de acompanhamento deve ter 4 dígitos e pertencer à tabela CO.
- **Pseudocódigo:**
  ```
  SE TIPO_n == "CO":
    SE len(IC_n) != 4 → ERRO("CO formato")
    SE IC_n NOT IN tabela_CO → ERRO("CO inexistente")
  ```
- **Entrada:** IC onde TIPO=CO
- **Tabela:** Aba CO 2026 (50 códigos)
- **Depende:** R020

#### R064 — CO de despesa associado a conta de despesa
- **Severidade:** ALERTA | **Prioridade:** P3
- **Lógica:** COs do bloco "Despesa Orçamentária" (1001-2xxx) só devem aparecer em contas de despesa. COs do bloco "Receita" (5001) só em contas de receita.
- **Pseudocódigo:**
  ```
  co_despesa = {1001..2999}
  co_receita = {5001..5999}
  SE CO IN co_despesa AND conta.classe NOT IN {5, 6, 1, 2} → ALERTA
  ```
- **Entrada:** CO + classe da conta
- **Depende:** R025

---

### CATEGORIA: NR (Natureza da Receita)

#### R026 — NR válida — 8 dígitos + tabela
- **Severidade:** ERRO | **Prioridade:** P2
- **Lógica:** A natureza da receita deve ter 8 dígitos e pertencer à tabela NR. Aplica-se a contas com ID_IC=6.
- **Pseudocódigo:**
  ```
  SE TIPO_n == "NR":
    SE len(IC_n) != 8 → ERRO("NR formato")
    SE IC_n NOT IN tabela_NR → ALERTA("NR desconhecida")
  ```
- **Entrada:** IC onde TIPO=NR
- **Tabela:** Aba NR 2026 (5450 códigos, 4504 valorizáveis)
- **Depende:** R020

#### R044 — NR deve ser valorizável (último nível)
- **Severidade:** ALERTA | **Prioridade:** P2
- **Lógica:** NR informada deve ser de nível valorizável (Valorizável=SIM). NRs sintéticas (NÃO) não devem receber valores.
- **Pseudocódigo:**
  ```
  SE tabela_nr[NR].Valorizavel == "NÃO" → ALERTA("NR sintética")
  ```
- **Entrada:** IC tipo NR + tabela NR 2026 (coluna Valorizável)
- **Depende:** R026

---

### CATEGORIA: ND (Natureza da Despesa)

#### R027 — ND válida — 8 dígitos + tabela
- **Severidade:** ERRO | **Prioridade:** P2
- **Lógica:** A natureza da despesa deve ter 8 dígitos e pertencer à tabela ND. Aplica-se a contas com ID_IC=7 ou 9.
- **Pseudocódigo:**
  ```
  SE TIPO_n == "ND":
    SE len(IC_n) != 8 → ERRO("ND formato")
    SE IC_n NOT IN tabela_ND → ALERTA("ND desconhecida")
  ```
- **Entrada:** IC onde TIPO=ND
- **Tabela:** Aba ND 2026 (1235 códigos, 1072 último nível)
- **Depende:** R020

#### R045 — ND deve ser de último nível
- **Severidade:** ALERTA | **Prioridade:** P2
- **Lógica:** ND informada deve ser de último nível (não Superior). NDs de nível Superior existem apenas para "De-Para".
- **Pseudocódigo:**
  ```
  SE tabela_nd[ND].Nivel.startswith("Superior") → ALERTA("ND sintética")
  ```
- **Entrada:** IC tipo ND + tabela ND 2026 (coluna Nível)
- **Depende:** R027

#### R046 — ND "Genérica" não deve ser usada na execução
- **Severidade:** ALERTA | **Prioridade:** P3
- **Lógica:** NDs com título "Modalidade Genérica" ou "Elemento Genérico" existem apenas para De-Para.
- **Pseudocódigo:**
  ```
  SE "Genéric" in tabela_nd[ND].Nome → ALERTA("ND genérica em execução")
  ```
- **Entrada:** IC tipo ND + tabela ND 2026 (coluna Nome)
- **Depende:** R027

#### R047 — Soma subelementos = elemento de despesa
- **Severidade:** ALERTA | **Prioridade:** P3
- **Lógica:** Quando uma ND tem desdobramentos em subelementos, a totalidade dos registros desdobrados deve corresponder ao valor do elemento de despesa pai.
- **Pseudocódigo:**
  ```
  PARA CADA elemento_nd (6 primeiros dígitos):
    valor_subs = SUM(registros com ND[:6] == elemento AND len(ND completa) > 6)
    valor_elem = SUM(registros com ND == elemento + "00")
    SE abs(valor_elem - valor_subs) > tolerancia → ALERTA
  ```
- **Entrada:** Registros ND agrupados por prefixo
- **Depende:** R027

---

### CATEGORIA: FS (Função/Subfunção)

#### R028 — FS válida — 5 dígitos (2 função + 3 subfunção)
- **Severidade:** ERRO | **Prioridade:** P2
- **Lógica:** A classificação funcional deve ter 5 dígitos. Função e subfunção devem existir nas tabelas.
- **Pseudocódigo:**
  ```
  SE TIPO_n == "FS":
    SE len(IC_n) != 5 → ERRO("FS formato")
    funcao = IC_n[:2]
    subfuncao = IC_n[2:]
    SE funcao NOT IN funcoes_validas → ERRO
    SE subfuncao NOT IN subfuncoes_validas → ALERTA
  ```
- **Entrada:** IC onde TIPO=FS
- **Tabela:** Aba FS
- **Depende:** R020

#### R065 — Subfunção pode combinar com qualquer função (INFO atípica)
- **Severidade:** INFO | **Prioridade:** P3
- **Lógica:** Conforme Portaria MOG 42/99, subfunções podem combinar com funções diferentes. Combinações atípicas merecem atenção.
- **Pseudocódigo:**
  ```
  # Verificar se combinação função×subfunção é típica ou atípica
  # Gerar INFO para combinações atípicas
  ```
- **Entrada:** IC tipo FS
- **Depende:** R028

---

### CATEGORIA: AI (Ano Inscrição RP)

#### R029 — AI válido — 4 dígitos, ano plausível
- **Severidade:** ALERTA | **Prioridade:** P2
- **Lógica:** O ano de inscrição de restos a pagar deve ter 4 dígitos e ser um ano plausível (2000 a ano corrente).
- **Pseudocódigo:**
  ```
  SE TIPO_n == "AI":
    SE len(IC_n) != 4 → ERRO("AI formato")
    SE int(IC_n) < 2000 OR int(IC_n) > ano_corrente → ALERTA("AI implausível")
  ```
- **Entrada:** IC onde TIPO=AI
- **Depende:** R020

---

### CATEGORIA: Fechamento Contábil

#### R030 — Débito = Crédito por conta (fechamento)
- **Severidade:** ERRO | **Prioridade:** P1
- **Lógica:** Para cada conta patrimonial (classes 1-4), soma dos movimentos devedores deve igualar soma dos credores.
- **Pseudocódigo:**
  ```
  PARA CADA conta em classes {1,2,3,4}:
    mov_D = SUM(Valor WHERE Tipo_valor="period_change" AND Natureza_valor="D")
    mov_C = SUM(Valor WHERE Tipo_valor="period_change" AND Natureza_valor="C")
    SE abs(mov_D - mov_C) > tolerancia → ERRO(conta, diferenca)
  ```
- **Entrada:** Valor + Tipo_valor + Natureza_valor por CONTA
- **Depende:** R010

#### R031 — Saldo Final = Saldo Inicial + Movimentos
- **Severidade:** ERRO | **Prioridade:** P1
- **Lógica:** Para contas devedoras: SF = SI + Mov_D - Mov_C. Para credoras: SF = SI + Mov_C - Mov_D.
- **Pseudocódigo:**
  ```
  PARA CADA combo CONTA+ICs:
    SI = Valor(beginning_balance)
    SF = Valor(ending_balance)
    mov_D = SUM(Valor(period_change, D))
    mov_C = SUM(Valor(period_change, C))
    SE nat_conta == "Devedora":
      SE abs(SF - (SI + mov_D - mov_C)) > tol → ERRO
    SE nat_conta == "Credora":
      SE abs(SF - (SI + mov_C - mov_D)) > tol → ERRO
  ```
- **Entrada:** Todos registros da conta/IC
- **Tabela:** PcaspEstendido2026 (NAT_SALDO)
- **Depende:** R010, R020

#### R032 — Natureza do saldo compatível com conta
- **Severidade:** ALERTA | **Prioridade:** P2
- **Lógica:** ending_balance deve ter Natureza_valor compatível com a natureza da conta no PCASP. Credora/Devedora aceita ambas.
- **Pseudocódigo:**
  ```
  nat_pcasp = pcasp[CONTA].NAT_SALDO
  SE nat_pcasp == "Devedora" AND saldo.Natureza_valor == "C" → ALERTA
  SE nat_pcasp == "Credora" AND saldo.Natureza_valor == "D" → ALERTA
  # "Credora/Devedora": ambos aceitos
  ```
- **Entrada:** ending_balance + PCASP.NAT_SALDO
- **Depende:** R010, R031

#### R035 — Débitos = Créditos — Patrimonial (classes 1-4)
- **Severidade:** ERRO | **Prioridade:** P1
- **Lógica:** Total de movimentos D deve igualar total C para o CONJUNTO de contas patrimoniais. Regra oficial do Siconfi — partidas dobradas.
- **Pseudocódigo:**
  ```
  mov_D = SUM(Valor WHERE classe IN {1,2,3,4} AND period_change AND D)
  mov_C = SUM(Valor WHERE classe IN {1,2,3,4} AND period_change AND C)
  SE abs(mov_D - mov_C) > tolerancia → ALERTA(diferenca)
  ```
- **Fonte:** Doc. Validações MSC (item e, conteúdo)
- **Depende:** R030

#### R036 — Débitos = Créditos — Orçamentário (classes 5-6)
- **Severidade:** ERRO | **Prioridade:** P1
- **Lógica:** Total D = Total C para contas orçamentárias (classes 5, 6).
- **Pseudocódigo:**
  ```
  mov_D = SUM(Valor WHERE classe IN {5,6} AND period_change AND D)
  mov_C = SUM(Valor WHERE classe IN {5,6} AND period_change AND C)
  SE abs(mov_D - mov_C) > tolerancia → ALERTA
  ```
- **Fonte:** Doc. Validações MSC (item e, conteúdo)
- **Depende:** R030

#### R037 — Débitos = Créditos — Controle (classes 7-8)
- **Severidade:** ERRO | **Prioridade:** P1
- **Lógica:** Total D = Total C para contas de controle (classes 7, 8).
- **Pseudocódigo:**
  ```
  mov_D = SUM(Valor WHERE classe IN {7,8} AND period_change AND D)
  mov_C = SUM(Valor WHERE classe IN {7,8} AND period_change AND C)
  SE abs(mov_D - mov_C) > tolerancia → ALERTA
  ```
- **Fonte:** Doc. Validações MSC (item e, conteúdo)
- **Depende:** R030

---

### CATEGORIA: Interconta

#### R050 — Ativo = Passivo + PL (equação patrimonial)
- **Severidade:** ERRO | **Prioridade:** P1
- **Lógica:** Soma dos saldos finais classe 1 (Ativo) deve igualar soma da classe 2 (Passivo+PL).
- **Pseudocódigo:**
  ```
  ativo = SUM(ending_balance classe 1, considerando Natureza_valor)
  passivo_pl = SUM(ending_balance classe 2, considerando Natureza_valor)
  SE abs(ativo - passivo_pl) > tolerancia → ERRO(diferença)
  ```
- **Depende:** R031

#### R051 — VPA - VPD = Resultado
- **Severidade:** ALERTA | **Prioridade:** P2
- **Lógica:** Soma de VPA (classe 4) deve ser consistente com VPD (classe 3) + resultado.
- **Pseudocódigo:**
  ```
  vpa = SUM(movimentos classe 4)
  vpd = SUM(movimentos classe 3)
  resultado = vpa - vpd
  # Verificar consistência com conta de resultado no PL
  ```
- **Depende:** R031

#### R052 — Controles devedores = Controles credores (7/8)
- **Severidade:** ALERTA | **Prioridade:** P3
- **Lógica:** Saldos finais da classe 7 devem igualar saldos finais da classe 8.
- **Pseudocódigo:**
  ```
  ctrl_D = SUM(ending_balance classe 7)
  ctrl_C = SUM(ending_balance classe 8)
  SE abs(ctrl_D - ctrl_C) > tolerancia → ALERTA
  ```
- **Depende:** R031

#### R053 — Contas INTRA OFSS com contrapartida
- **Severidade:** ALERTA | **Prioridade:** P3
- **Lógica:** Contas com "INTRA OFSS" no título devem ter contrapartida. Se existe débito INTRA, deve existir crédito INTRA correspondente.
- **Pseudocódigo:**
  ```
  contas_intra = filtrar(pcasp WHERE TITULO_DESC contains "INTRA")
  # Verificar existência de contrapartida para cada INTRA com saldo
  ```
- **Depende:** R010

---

### CATEGORIA: Superávit Financeiro

#### R060 — FP coerente com indicador PCASP
- **Severidade:** ALERTA | **Prioridade:** P2
- **Lógica:** Quando a conta tem IND_SF definido no PCASP, o FP informado deve ser compatível.
- **Pseudocódigo:**
  ```
  ind_sf = pcasp[CONTA].IND_SF
  SE ind_sf == "Financeiro" AND FP != "1" → ALERTA
  SE ind_sf == "Permanente" AND FP != "2" → ALERTA
  # "Financeiro/Permanente": aceita 1 ou 2
  ```
- **Entrada:** FP + PCASP.IND_SF
- **Depende:** R020, R022

#### R061 — Conta exclusivamente Financeira com FP=2
- **Severidade:** ALERTA | **Prioridade:** P2
- **Lógica:** Contas cujo IND_SF é "Financeiro" não devem ter FP=2 (Permanente).
- **Pseudocódigo:**
  ```
  SE pcasp[CONTA].IND_SF == "Financeiro" AND FP == "2" → ALERTA
  ```
- **Depende:** R022, R060

#### R062 — Conta exclusivamente Permanente com FP=1
- **Severidade:** ALERTA | **Prioridade:** P2
- **Lógica:** Contas cujo IND_SF é "Permanente" não devem ter FP=1 (Financeiro).
- **Pseudocódigo:**
  ```
  SE pcasp[CONTA].IND_SF == "Permanente" AND FP == "1" → ALERTA
  ```
- **Depende:** R022, R060

---

### CATEGORIA: Completude

#### R040 — Contas patrimoniais têm saldo inicial
- **Severidade:** ALERTA | **Prioridade:** P2
- **Lógica:** Contas patrimoniais (classes 1, 2, 5, 6) devem ter pelo menos um beginning_balance.
- **Pseudocódigo:**
  ```
  PARA CADA conta patrimonial (classe IN {1,2,5,6}):
    SE COUNT(Tipo_valor="beginning_balance") == 0 → ALERTA
  ```
- **Depende:** R010

#### R041 — Contas patrimoniais têm saldo final
- **Severidade:** ALERTA | **Prioridade:** P2
- **Lógica:** Contas patrimoniais devem ter pelo menos um ending_balance.
- **Pseudocódigo:**
  ```
  PARA CADA conta patrimonial:
    SE COUNT(Tipo_valor="ending_balance") == 0 → ALERTA
  ```
- **Depende:** R010

#### R042 — Contas de resultado sem saldo (apenas movimentos)
- **Severidade:** ALERTA | **Prioridade:** P3
- **Lógica:** Contas de resultado (classes 3, 4) normalmente não devem ter beginning_balance nem ending_balance, apenas period_change.
- **Pseudocódigo:**
  ```
  PARA CADA conta resultado (classe IN {3,4}):
    SE EXISTS(Tipo_valor IN {"beginning_balance", "ending_balance"}) → ALERTA
  ```
- **Depende:** R010

#### R043 — Valor zerado sem movimentos
- **Severidade:** INFO | **Prioridade:** P3
- **Lógica:** Contas com todos valores = 0 podem indicar lançamento desnecessário.
- **Pseudocódigo:**
  ```
  PARA CADA conta:
    SE SUM(abs(Valor)) == 0 → INFO("conta totalmente zerada")
  ```
- **Depende:** R010

#### R066 — Existe pelo menos 1 conta de receita (com NR)
- **Severidade:** ALERTA | **Prioridade:** P3
- **Lógica:** Um ente deve ter receitas orçamentárias. Se nenhuma conta com NR existir, pode indicar problema.
- **Pseudocódigo:**
  ```
  SE COUNT(registros WHERE TIPO_n == "NR") == 0 → ALERTA
  ```
- **Depende:** R026

#### R067 — Existe pelo menos 1 conta de despesa (com ND)
- **Severidade:** ALERTA | **Prioridade:** P3
- **Lógica:** Um ente deve ter despesas orçamentárias.
- **Pseudocódigo:**
  ```
  SE COUNT(registros WHERE TIPO_n == "ND") == 0 → ALERTA
  ```
- **Depende:** R027

#### R068 — Existem contas de todas as 8 classes
- **Severidade:** ALERTA | **Prioridade:** P3
- **Lógica:** Ausência de uma classe inteira pode indicar problema sistêmico.
- **Pseudocódigo:**
  ```
  classes_presentes = set(CONTA.str[0])
  faltantes = {"1","2","3","4","5","6","7","8"} - classes_presentes
  SE faltantes → ALERTA(f"classes ausentes: {faltantes}")
  ```
- **Depende:** R010

#### R074 — Cada conta/IC deve ter ending_balance OU period_change
- **Severidade:** ALERTA | **Prioridade:** P3
- **Lógica:** Registros apenas com beginning_balance (sem SF nem movimentos) são inúteis.
- **Pseudocódigo:**
  ```
  PARA CADA chave (CONTA+ICs):
    SE set(Tipo_valor) == {"beginning_balance"} → ALERTA
  ```
- **Depende:** R003

---

### CATEGORIA: Temporal

#### R054 — Saldo inicial mês N = saldo final mês N-1
- **Severidade:** ALERTA | **Prioridade:** P2
- **Lógica:** Ao processar meses consecutivos, beginning_balance(N) deve igualar ending_balance(N-1).
- **Pseudocódigo:**
  ```
  SE existe_snapshot_anterior:
    PARA CADA conta/IC:
      SE abs(SI_atual - SF_anterior) > tol → ALERTA(conta, diferença)
  ```
- **Depende:** R031

#### R055 — Contas resultado (3/4) zeradas no mês 01
- **Severidade:** ALERTA | **Prioridade:** P3
- **Lógica:** Em janeiro, contas de resultado devem começar com saldo inicial zero.
- **Pseudocódigo:**
  ```
  SE periodo.mes == "01":
    PARA CADA conta classe {3,4}:
      SE beginning_balance != 0 → ALERTA
  ```
- **Depende:** R040

#### R069 — MSC encerramento (mês 13) com resultado zerado
- **Severidade:** ALERTA | **Prioridade:** P2
- **Lógica:** Na MSC-13, contas de resultado (classes 3, 4) devem estar zeradas.
- **Pseudocódigo:**
  ```
  SE periodo.mes == "13":
    PARA CADA conta classe {3,4}:
      SE ending_balance != 0 → ALERTA("resultado não encerrado")
  ```
- **Depende:** R041

---

### CATEGORIA: Duplicidade

#### R070 — Sem registros duplicados
- **Severidade:** ERRO | **Prioridade:** P1
- **Lógica:** Não deve haver duas linhas com a mesma combinação de CONTA + ICs + Tipo_valor + Natureza_valor.
- **Pseudocódigo:**
  ```
  chave = (CONTA, IC1..IC6, Tipo_valor, Natureza_valor)
  duplicatas = df[df.duplicated(subset=chave, keep=False)]
  SE len(duplicatas) > 0 → ERRO("registros duplicados", indices)
  ```
- **Depende:** R001

---

### CATEGORIA: Formato

#### R080 — CONTA tem 9 dígitos numéricos
- **Severidade:** ERRO | **Prioridade:** P0
- **Lógica:** O código da conta contábil deve ter exatamente 9 dígitos numéricos.
- **Pseudocódigo:**
  ```
  SE len(CONTA) != 9 OR NOT CONTA.isdigit() → ERRO("formato inválido")
  ```
- **Depende:** R001

#### R081 — IC tem dígitos no formato correto
- **Severidade:** ERRO | **Prioridade:** P1
- **Lógica:** Cada IC deve ter o número de dígitos esperado pelo seu TIPO.
- **Pseudocódigo:**
  ```
  mapa = {"PO":5, "FP":1, "DC":1, "FR":4, "CO":4, "NR":8, "ND":8, "FS":5, "AI":4}
  SE len(IC_n) != mapa[TIPO_n] → ERRO(TIPO, esperado, encontrado)
  ```
- **Entrada:** IC1–IC6 + TIPO1–TIPO6
- **Depende:** R001

---

### CATEGORIA: Qualidade

#### R071 — Valores com centavos plausíveis
- **Severidade:** INFO | **Prioridade:** P3
- **Lógica:** Valores com mais de 2 casas decimais podem indicar erro de conversão.
- **Pseudocódigo:**
  ```
  SE decimais(Valor) > 2 → INFO("valor com >2 decimais")
  ```
- **Depende:** R005

#### R072 — Conta com muitos registros (outlier estatístico)
- **Severidade:** INFO | **Prioridade:** P3
- **Lógica:** Conta com quantidade de registros > média + 3σ pode indicar duplicação parcial.
- **Pseudocódigo:**
  ```
  contagem = df.groupby("CONTA").size()
  SE contagem[CONTA] > media + 3 * std → INFO("registros atípicos")
  ```
- **Depende:** R070

#### R073 — Valor muito grande (outlier absoluto)
- **Severidade:** INFO | **Prioridade:** P3
- **Lógica:** Valores extremamente altos podem indicar erro de escala.
- **Pseudocódigo:**
  ```
  SE Valor > percentil_99 * 10 → INFO("valor outlier")
  ```
- **Depende:** R005
