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

1. Abra o aplicativo pelo atalho do menu iniciar ou da area de trabalho.
2. Informe e-mail e senha.
3. A tela inicial sera aberta em **Inicio**.

Se o login expirar, o sistema volta para a tela de login. Entre novamente e
continue a consulta.

### Entrar com convite

Se voce recebeu por e-mail um convite do responsavel tecnico (com o link do
instalador e um codigo), seu primeiro acesso e assim:

1. Baixe o instalador pelo link do e-mail e instale o MCRA.
2. Abra o aplicativo. Na tela de entrada, clique em **Tenho um convite**.
3. Copie o codigo do e-mail e cole no campo **Codigo do convite** (pode colar o
   texto inteiro, mesmo que ocupe varias linhas).
4. Escolha a **senha** (de 8 a 72 caracteres) e repita em **Confirmar senha**.
5. Clique em **Entrar com convite**. O aplicativo abre direto em **Inicio**.

Nas proximas vezes, entre com o e-mail que recebeu o convite e a senha que voce
escolheu.

O convite tem prazo de validade (o prazo vem escrito no e-mail) e so pode ser
usado uma vez em cada computador. Se a tela disser que o convite venceu ou ja foi usado, peca um novo ao responsavel
tecnico. Se o botao **Tenho um convite** nao aparece, a sua versao do
aplicativo ainda nao tem convites: procure o responsavel tecnico.

### Trocar a senha

Entrou com a senha que veio no e-mail e quer outra? Clique em **Trocar senha**,
no rodape do menu lateral (acima de **Sair**). Digite a senha atual, a nova (8
caracteres ou mais) e repita a nova. Voce continua conectado; a senha nova vale
a partir da proxima entrada.

### Esqueci a senha

Peca um novo convite ao responsavel tecnico e siga os passos de "Entrar com
convite" acima: o codigo troca a senha da sua conta, e voce escolhe a nova. Seus
dados (snapshots, relatorios, logs) continuam onde estavam.

Se a sua versao do aplicativo ainda nao tem **Tenho um convite**, o responsavel
tecnico segue o procedimento do guia de operacao (`doc/guia_operacao.md`).

### Convidar colaboradores (so para quem e o responsavel pelos convites)

Tudo e feito no proprio aplicativo; nao precisa instalar mais nada.

1. Entre com o seu login e abra **Convidar** no menu.
2. **Primeira vez:** aparece "Ativar os convites neste computador". Cole o
   codigo de ativacao que o responsavel tecnico enviou (comeca com
   `MCRA-ATIVACAO1`), informe a **conta do Gmail** que envia os convites e a **senha de app** dela
   (gerada em myaccount.google.com/apppasswords, com a verificacao em duas
   etapas ligada; nao e a senha normal do Gmail). Clique em **Ativar convites**.
3. Para convidar: digite so o e-mail do colaborador e clique em **Enviar
   convite**. Ele recebe o link do instalador e o codigo.
4. Trocou a senha de app ou a conta do Gmail? **Trocar conta ou senha de app do
   Gmail**. Se o app pedir para ativar de novo, **Ativar de novo** com o mesmo
   codigo.

Guarde o codigo de ativacao em lugar seguro: com ele voce ativa de novo se
trocar de computador.

---

## Fluxo recomendado

1. Entrar no sistema.
2. Ir em **Inicio**.
3. Enviar o CSV da MSC do mes.
4. Aguardar o processamento terminar.
5. Revisar score, principais regras e pendencias.
6. Abrir **Pendencias** para filtrar por regra, severidade ou conta.
7. Usar **Regras** e o drawer de detalhes para entender o motivo da pendencia.
8. Exportar Excel/PDF quando precisar compartilhar evidencias. Ao clicar em
   exportar (ou em **Emitir relatorio**, na tela Meu tempo de uso), o Windows
   abre a janela "Salvar como" ja na pasta Downloads: confirme o nome e salve.
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
  retificadas (o resumo so aparece quando ha dado para mostrar - ver abaixo
  o que acontece quando o Siconfi esta indisponivel e nao ha cache);
- "Entregas com prazo acompanhado": entregas cujo entregavel tem prazo
  configurado no sistema. O extrato do Siconfi so contem o que ja foi
  entregue - esta secao nao lista pendencia futura, mostra a situacao de
  prazo do que ja foi enviado;
- "Como estamos": tabela por instituicao (Prefeitura e Camara), com status,
  periodo, data e dias decorridos apos o fim do periodo de cada entrega.

**Retificado** significa que o ente reenviou o relatorio depois do envio
original, substituindo os dados homologados anteriormente. Cada retificacao
conta no resumo e e um dos fatores que a Dimensao I do Ranking penaliza -
quanto mais retificacoes, pior a nota dessa dimensao. Um relatorio aparece
como `HOMOLOGADO` quando foi aceito sem retificacao posterior.

**Por que um relatorio RETIFICADO nao mostra dias-apos-o-prazo:** a data que
o Siconfi devolve para um relatorio retificado (`data_status`) e a data da
RETIFICACAO, nao da entrega original - que pode ter sido feita meses antes e
nao vem no extrato da API. Por isso, para RETIFICADO, a coluna de prazo
mostra "retificado em DD/MM/AAAA" em vez de dias decorridos: mostrar dias
contados a partir dessa data daria a entender, errado, que a entrega
original atrasou. Para conferir a data e o codigo bruto (`HO`/`RE`) que a
API devolveu, veja a coluna **Data** e passe o mouse sobre o status na
tabela.

**Por que alguns entregaveis nao mostram situacao de prazo:** a coluna de
dias mostra os dias decorridos desde o fim do periodo para toda entrega
HOMOLOGADA, mas so emite um veredicto ("no prazo" / "fora do prazo") para os
entregaveis que tem prazo configurado no sistema. DCA, MSC Agregada e MSC
Encerramento aparecem **sem** esse veredicto de proposito: ainda nao
conseguimos fundamentar o prazo desses tres entregaveis em norma especifica,
e preferimos mostrar so o dado factual (dias decorridos) a arriscar um
julgamento errado. Isso nao e falta de dado nem erro da tela - e uma escolha
deliberada, ate que a contabilidade confirme os prazos aplicaveis.

Quando o Siconfi nao responde, a tela mostra um aviso no topo e continua
funcionando com o ultimo dado salvo em cache (quando existir). Um horario do
tipo "atualizado ha Xh" indica a idade do dado exibido. Quando nao ha Siconfi
nem cache disponivel, a tela mostra so o aviso explicando a indisponibilidade
- sem resumo nem tabelas, para nao dar a entender que "0 retificacoes" e um
resultado real.

### Ajuda

Tela com perguntas e respostas do dia a dia (login, convite por e-mail, envio da MSC, score,
pendencias, regras, exportacoes, senha esquecida e antivirus), cada uma com
passo a passo e uma animacao curta. Abre pelo grupo **Ajuda** no menu lateral
ou, antes do login, pelo link **Precisa de ajuda?** na tela de entrada; nao
exige estar logado. O mesmo conteudo existe como arquivo unico
`FAQ-MCRA.html` (gerado com `make faq-html`), que pode ser aberto no navegador
sem instalar nada.

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
| Login nao entra | Conferir e-mail/senha com o responsavel tecnico. |
| Esqueci a senha | Pedir um novo convite ao responsavel tecnico (ver "Esqueci a senha"). |
| Convite venceu ou "ja foi usado" | Pedir um novo convite ao responsavel tecnico. |
| Codigo do convite "invalido" | Copiar o codigo inteiro do e-mail e colar de novo. |
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
