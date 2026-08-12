# Calibração das regras — respostas do Rodrigo

**Respondido em:** 11/08/2026 08:07
**Formulário:** `doc/perguntas_rodrigo_calibracao_regras.md`
**Fontes que ele indicou:** `ref/2026_Leiaute_MSC_STN_anexo_28661.xlsx` (leiaute MSC 2026
completo) e `ref/IPC_Encerramento_STN.pdf` (procedimento de encerramento, p. 9).

Doze verificações do motor estavam disparando nos arquivos reais de João Pessoa sem que
soubéssemos separar inconsistência real de rigor excessivo nosso. Este documento registra
o que a contabilidade respondeu e o que cada resposta mudou no código.

## 1. Fonte de Recursos ausente (R020)

**Resposta:** "Não — há situações em que FR é dispensado, mesmo em conta que normalmente o
exige." Campo aberto: "Em contas com atributo P".

O atributo é a IC `FP` do leiaute (1 = Financeiro, 2 = Permanente). Nas três amostras de JP,
nenhuma linha com `FP = 1` está sem FR; todas as linhas sem FR que informam FP têm `FP = 2`.
As duas contas citadas no formulário (`113119900` e `211110102`) têm `FP = 2`.

**Mudança:** FR deixa de ser exigido em conta cujas linhas informam exclusivamente `FP = 2`.
Severidade segue ERRO nos demais casos.

## 2. Onde fica o resultado antes do encerramento (R051)

**Resposta:** "Fica em 2.3.x (Patrimônio Líquido) — nossa verificação está olhando o grupo
errado." Campo aberto: "2.3.7. O confronto entre VPA - VPD é realizado no encerramento de
exercício. As contas são zeradas em confronto com a conta Resultados Acumulados."

**Mudança:** o grupo comparado passa de 2.1.4 para 2.3.7 e a comparação só roda na
competência de encerramento (mês 13).

## 3. Natureza da Despesa em nível de elemento (R045)

**Resposta:** "O elemento com subelemento 00 é nível de execução válido — pode empenhar
assim." Campo aberto: "Na execução há indicação de subelemento. Entretanto, há elementos que,
para fins de envio para o SICONFI, pode haver o envio no subelemento 00. O regramento é o
constante no layout disponibilizado pelo Tesouro Nacional."

Dos códigos que a regra acusava, 76 são `Superior 4º Nível - Elemento` — o caso liberado — e
86 são `Superior` de Classe, Grupo ou Modalidade.

**Mudança:** a regra ignora `Superior 4º Nível - Elemento` e acusa só os níveis acima de
elemento.

## 4. Naturezas de Despesa genéricas (R046)

**Resposta:** "Há NDs nessa lista que são de uso legítimo", com o workbook oficial como
referência.

As 77 NDs que marcávamos como genéricas pelo nome estão classificadas na tabela oficial
como último nível: 70 `Último 4º Nível - Elemento`, 6 `Último 3º Nível - Modalidade` e 1
`Último 5º Nível - Subelemento`. `31309900 ELEMENTO GENÉRICO` é o exemplo mais direto. A
regra era falso positivo em todos os casos.

**Mudança:** severidade INFO e fora da pontuação. Quem manda sobre o que pode ser enviado é
a coluna `nivel` da tabela oficial, não o nome da ND.

## 5. Contas de controle sem ND e sem FS (R091, R092)

**Resposta:** "Depende." Campo aberto: "As informações complementares para a classe 6
(execução de despesa) são PO, FS, FR, CO e ND."

É exatamente o ID_IC 7 do leiaute, e a conta `622310000` que as regras acusam tem ID_IC 7 no
PCASP Estendido.

**Mudança: nenhuma.** As duas regras estão corretas e os 76 casos de cada uma são pendência
real. A suspeita de rigor excessivo fica registrada aqui como descartada.

## 6. Elemento e subelementos da despesa (R047)

**Resposta:** "Nenhum dos dois; a relação correta é outra." Campo aberto: "Podem existir
elementos que não sejam detalhados."

Não há relação aritmética exigível entre o elemento pai e seus subelementos, porque parte da
despesa pode ser enviada sem detalhamento.

**Mudança:** severidade INFO e fora da pontuação. O confronto continua no relatório.

## 7. Versão da tabela de Natureza da Receita (R026)

**Resposta:** "Depende." Campo aberto: "O Tesouro Nacional atualiza, pontualmente, NR,
acrescentando ou excluindo itens."

O código `13210101` citado no formulário não existe nem na nossa tabela nem no workbook
oficial atualizado: é de uma versão anterior, usada numa competência de 2025. Não temos a
tabela histórica.

**Mudança:** o código ausente da tabela vira INFO quando o ano da competência é anterior ao
ano das tabelas de referência. Comprimento e formato seguem ERRO em qualquer competência.

## 8. Contrapartida em contas de controle (R064)

**Resposta:** "Depende." Campo aberto: "Vai depender de previsão expressa no layout SICONFI."

A conta `721900000`, que a regra acusava, tem ID_IC 5 (`PO - FR - CO`) no PCASP Estendido: o
leiaute prevê CO nela de forma expressa. A restrição por classe contábil que aplicávamos não
está no leiaute, e a R020 já cobre a conformidade do conjunto de IC de cada conta.

**Mudança:** severidade INFO e fora da pontuação.

## 9. Contas patrimoniais sem saldo inicial ou final (R040, R041)

**Resposta:** "Não — conta nova no período ou conta zerada pode não ter uma das entradas."

**Mudança:** severidade INFO e fora da pontuação nas duas regras.

## 10. Saldo em contas de resultado durante o exercício (R042)

**Resposta:** "Podem sim — acumulam durante o exercício e zeram no encerramento."

**Mudança:** em vez de desligar a regra, ela passa a verificar o que a resposta afirma: nada
durante o exercício, e ALERTA no encerramento (mês 13) para conta de classe 3 ou 4 cujo saldo
final não zerou. É o procedimento do IPC de Encerramento, p. 9.

## Fechamento

A pergunta final ("alguma verificação que deveríamos estar fazendo e não mencionamos?") veio
sem resposta.
