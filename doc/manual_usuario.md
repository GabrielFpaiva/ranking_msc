# Manual do Usuario - Ranking MSC

> Publico: equipe contabil, controladoria e usuarios internos que validam a MSC.
> Versao operacional: React + FastAPI, com autenticacao por login.

---

## Objetivo

O Ranking MSC valida o arquivo mensal da Matriz de Saldos Contabeis (MSC),
aponta pendencias por regra, calcula uma nota de conformidade e gera relatorios
para apoiar a correcao antes do envio/fechamento.

O sistema nao substitui a analise contabil. Ele organiza evidencias tecnicas e
prioriza riscos para a equipe revisar.

---

## Acesso

1. Abra a URL disponibilizada pela TI ou pela controladoria.
2. Informe usuario e senha.
3. A tela inicial sera aberta em **Inicio**.

Se o login expirar, o sistema volta para a tela de login. Entre novamente e
continue a consulta.

---

## Fluxo recomendado

1. Entrar no sistema.
2. Ir em **Inicio**.
3. Enviar o CSV da MSC do mes.
4. Aguardar o processamento terminar.
5. Revisar score, principais regras e pendencias.
6. Abrir **Pendencias** para filtrar por regra, severidade ou conta.
7. Usar **Regras** e o drawer de detalhes para entender o motivo da pendencia.
8. Exportar Excel/PDF quando precisar compartilhar evidencias.
9. Comparar competencias anteriores em **Comparar** quando houver historico.

---

## Arquivo MSC esperado

O arquivo de entrada deve ser CSV da MSC, com:

- linha de metadados com SICONFI e competencia;
- cabecalho MSC na linha seguinte;
- separador esperado por ponto e virgula;
- contas, indicadores complementares, tipo de valor, natureza e valor.

Competencia esperada: `YYYY-MM`, por exemplo `2026-01`.

Se o arquivo estiver vazio, sem metadata, com separador incorreto ou cabecalho
fora do formato esperado, o sistema retorna erro de leitura ou gera pendencias
de estrutura.

---

## Telas

### Inicio

Use para enviar uma nova MSC e ver o resumo da ultima execucao.

Depois do upload, a tela mostra:

- status da execucao;
- competencia e SICONFI identificados;
- total de pendencias;
- score geral e banda;
- principais regras violadas.

Se outra pessoa ja estiver processando o mesmo SICONFI e a mesma competencia, o
sistema rejeita a nova execucao temporariamente para evitar sobrescrita de
resultados. Aguarde a execucao atual terminar e tente novamente.

### Execucao

Use para acompanhar informacoes de execucao e logs. Esta tela ajuda a verificar
se o processamento terminou, se houve erro e qual foi o identificador da
execucao.

### Regras

Lista o catalogo de regras e a visao de ocorrencias por competencia.

Ao abrir uma regra, o drawer mostra:

- nome da regra;
- dimensao;
- descricao;
- historico/ocorrencias quando houver dados processados.

### Pendencias

Tela principal para trabalho de correcao.

Filtros disponiveis:

- regra, por exemplo `R020`;
- severidade: `ERRO`, `ALERTA`, `INFO`;
- prefixo de conta contabil;
- paginacao.

Severidades:

- `ERRO`: bloqueio ou inconsistencia relevante que deve ser priorizada.
- `ALERTA`: possivel problema ou situacao que exige revisao.
- `INFO`: achado informativo ou qualidade de dado.

Use o Excel exportado quando precisar trabalhar com grande volume de linhas.

### Caixa

Mostra contas de caixa e equivalentes filtradas por prefixos contabeis
configurados no sistema. Use para conferir saldos iniciais, finais e movimento
liquido.

### Passivos

Mostra contas de passivo circulante e nao circulante. Os saldos sao consolidados
para facilitar revisao de obrigacoes e inversoes de natureza.

### Superavit

Mostra resultado financeiro por Fonte de Recursos (FR).

Calculo operacional usado na versao atual:

- considera linhas com FR informada;
- cruza contas com PCASP;
- considera contas classificadas como financeiras;
- calcula ativo financeiro, passivo financeiro e resultado por FR.

O resultado deve ser validado pela area contabil, especialmente se houver
necessidade de tratar contas classificadas como `Financeiro/Permanente`.

### Executivo

Visao sintetica para acompanhamento gerencial.

Mostra score, banda, dimensoes mais fracas, historico e recomendacoes geradas a
partir das pendencias.

Use o PDF executivo para reunioes e comunicacao resumida.

### Comparar

Compara duas competencias do mesmo ente.

Use para verificar:

- variacao do score;
- reducao ou aumento de pendencias;
- dimensoes que melhoraram ou pioraram.

E necessario ter snapshots processados para as competencias escolhidas.

### Entregas

Mostra o extrato de entregas ao Siconfi (Dimensao I do Ranking) para o
exercicio selecionado: quais relatorios foram enviados, quando, e se houve
retificacao.

Selecione o **exercicio** no topo da tela. A tela mostra:

- resumo do exercicio: total de entregas, quantas homologadas e quantas
  retificadas;
- "O que vence agora": entregas com prazo configurado ainda em aberto;
- "Como estamos": tabela por instituicao (Prefeitura e Camara), com status,
  periodo e dias decorridos apos o fim do periodo de cada entrega.

**Retificado** significa que o ente reenviou o relatorio depois do envio
original, substituindo os dados homologados anteriormente. Cada retificacao
conta no resumo e e um dos fatores que a Dimensao I do Ranking penaliza -
quanto mais retificacoes, pior a nota dessa dimensao. Um relatorio aparece
como `HOMOLOGADO` quando foi aceito sem retificacao posterior.

**Por que alguns entregaveis nao mostram situacao de prazo:** a coluna de
prazo mostra os dias decorridos desde o fim do periodo para toda entrega, mas
so emite um veredicto ("no prazo" / "fora do prazo") para os entregaveis que
tem prazo configurado no sistema. DCA, MSC Agregada e MSC Encerramento
aparecem **sem** esse veredicto de proposito: ainda nao conseguimos
fundamentar o prazo desses tres entregaveis em norma especifica, e preferimos
mostrar so o dado factual (dias decorridos) a arriscar um julgamento errado.
Isso nao e falta de dado nem erro da tela - e uma escolha deliberada, ate que
a contabilidade confirme os prazos aplicaveis.

Quando o Siconfi nao responde, a tela mostra um aviso no topo e continua
funcionando com o ultimo dado salvo em cache (quando existir). Um horario do
tipo "atualizado ha Xh" indica a idade do dado exibido.

---

## Exportacoes

### Excel de pendencias

Gerado apos o processamento da MSC.

Conteudo principal:

- resumo por severidade e dimensao;
- lista completa de pendencias;
- evidencias por regra, conta e valores esperados/encontrados;
- aba de score quando aplicavel.

### PDF executivo

Gerado sob demanda a partir dos snapshots ja processados.

Conteudo principal:

- score geral;
- banda;
- historico recente;
- dimensoes criticas;
- recomendacoes.

---

## Como interpretar o score

O score varia de 0 a 100 e usa bandas:

| Banda | Faixa |
|---|---|
| A | 95 a 100 |
| B | 85 a 94,99 |
| C | 75 a 84,99 |
| D | 65 a 74,99 |
| E | abaixo de 65 |

O score deve ser usado como priorizacao. Uma nota alta nao dispensa revisao de
pendencias criticas, e uma nota baixa indica que a equipe deve priorizar regras
com `ERRO` e dimensoes mais fracas.

---

## Problemas comuns

| Situacao | O que fazer |
|---|---|
| Login nao entra | Conferir usuario/senha com o operador do sistema. |
| Arquivo vazio | Exportar novamente o CSV da MSC. |
| Erro de formato | Conferir metadata, separador e cabecalho do CSV. |
| Sem historico para comparar | Processar as competencias anteriores. |
| Excel nao baixa | Confirmar se a MSC foi processada para aquele SICONFI/competencia. |
| PDF nao gera | Confirmar se existe snapshot de resultado para a competencia. |
| Execucao em andamento | Aguardar a execucao atual terminar e reenviar depois. |

---

## Informacoes para suporte

Ao reportar problema, informe:

- usuario;
- SICONFI;
- competencia;
- nome do arquivo enviado;
- horario aproximado;
- mensagem exibida na tela;
- `execucao_id`, se aparecer.
