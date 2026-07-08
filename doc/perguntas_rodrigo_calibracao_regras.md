# Perguntas para o Rodrigo — Calibração de Regras (validação MSC)

> **Contexto:** João Pessoa (ente 2507507) obteve no Ranking Siconfi oficial
> **banda A, 4º lugar, 99,795% (194.600 pts)** com os arquivos MSC de teste
> (competências 2025-12 e 2025-13). Nosso motor, porém, ainda pontua **~85
> (banda C)** nesses mesmos arquivos — ou seja, ele **super-sinaliza**.
>
> Já corrigimos 3 regras que eram falso-positivo comprovado por matemática/norma:
> - **R030** (partidas dobradas: era por conta, agora é global do razão);
> - **R020** (conjunto de IC: agora usa a união das linhas da conta; CO tratado
>   como condicional — "quando se aplicar", Anexo II);
> - **R050** (equação patrimonial: agora usa a forma estendida
>   `Ativo(1)+VPD(3) = Passivo+PL(2)+VPA(4)`, válida antes do encerramento).
>
> As regras abaixo ainda disparam no gabarito de JP. Como o resultado oficial é
> ~99,8%, elas são **suspeitas de falso-positivo**, mas a correção depende de
> definição contábil/normativa. Cada item traz o que a regra faz, o que
> observamos e a **pergunta objetiva**.

---

## 1. Resultado do exercício antes do encerramento

### R051 — VPA − VPD = variação dos Resultados Acumulados
- **O que faz:** compara o resultado do período (VPA − VPD, classes 4 e 3) com a
  variação de saldo do grupo **2.1.4** (que a regra assume ser "Resultados
  Acumulados").
- **O que observamos:** VPA−VPD = R$ 71,4 mi (2025-12), mas a variação do grupo
  **2.1.4 = R$ 0,00** — em **todas** as competências, inclusive no encerramento.
  No PCASP, o grupo **2.1.4 é Passivo Circulante**; os Resultados
  Acumulados/Superávit do Exercício ficam no **Patrimônio Líquido (2.3.x)**.
- **❓ Pergunta:** Em qual conta/grupo do PCASP de João Pessoa fica registrado o
  **Superávit/Déficit e os Resultados Acumulados do exercício** (é `2.3.x`?)? E
  essa conciliação (VPA−VPD = variação do resultado acumulado) **só deve fechar
  no encerramento anual**, ou também mês a mês?

### R042 — Contas de resultado sem saldo (só movimento)
- **O que faz:** alerta quando uma conta de resultado (classes 3 e 4) tem
  lançamento de **saldo inicial ou final** (deveria ter só `period_change`).
- **O que observamos:** 166 contas de resultado de JP têm saldo inicial/final
  (com valor, não zero). Elas acumulam saldo ao longo do ano e zeram no
  encerramento — e o arquivo foi aceito como conforme.
- **❓ Pergunta:** No leiaute MSC, contas de VPD/VPA (classes 3 e 4) **podem/devem
  reportar saldo inicial e final durante o exercício**, ou realmente só
  `period_change`? Se podem ter saldo, essa regra deve ser desativada/reclassificada.

---

## 2. Natureza da Despesa (ND) e Função/Subfunção (FS)

### R045 — ND deve ser de último nível
- **O que faz:** alerta quando a ND informada consta como nível **"Superior"
  (sintético)** na tabela ND, não como "Último".
- **O que observamos:** dispara em NDs como `33504300` e `33913900` (subelemento
  `00`). A tabela ND 2026 as classifica como "Superior 4º Nível - Elemento".
- **❓ Pergunta:** Para essas despesas, o **elemento com subelemento `00`** é um
  nível de execução **válido/terminal** (ou seja, JP pode empenhar em `33504300`),
  ou deveria sempre detalhar um subelemento (`335043xx`)?

### R046 — ND não deve ser genérica (De-Para)
- **❓ Pergunta:** A lista de NDs "genéricas" que a regra rejeita está atualizada
  para 2026? Há NDs que JP usa legitimamente e que a regra trata como genéricas?

### R091 / R092 — Despesa orçamentária sem ND / sem FS
- **O que faz:** exige ND (R091) e FS (R092) em contas de despesa orçamentária
  (ID_IC 7 ou 9).
- **O que observamos:** dispara em contas de **classe 6** (controle), ex.
  `622310000`, que não têm ND/FS em nenhuma linha.
- **❓ Pergunta:** Todas as contas de classe 6 com ID_IC 7/9 **obrigatoriamente
  carregam ND e FS**, ou há contas de controle (ex. `6.2.2.3.1…`) que
  legitimamente não têm ND/FS?

### R047 — Soma dos subelementos = elemento pai (ND)
- **O que faz:** para uma ND com subelementos, exige que a soma dos subelementos
  **iguale** o valor do elemento pai (subelemento `00`).
- **O que observamos:** no prefixo `339040`, subelementos somam **+96,88 mi** e o
  elemento pai marca **−96,88 mi** (mesmo valor, **sinal oposto**) — ou seja,
  eles **se anulam** (somam zero), em vez de serem iguais.
- **❓ Pergunta:** No controle da execução da despesa, o elemento pai e os
  subelementos devem **ser iguais** ou **somar zero** (lançamentos em lados
  opostos)? Isso define se invertemos a regra.

---

## 3. Natureza da Receita (NR) e Contrapartida (CO)

### R026 — NR deve existir na tabela NR 2026
- **O que observamos:** NR `13210101` (conta `521110000`) **não consta** nem na
  nossa tabela nem no Anexo II 2026 — parece código de versão anterior.
- **❓ Pergunta:** A NR `13210101` é válida para a competência 2025-12 (versão de
  tabela NR vigente naquele período), ou é realmente um código inválido? Ou seja,
  a validação deve usar a tabela **da competência** e não sempre a de 2026?

### R064 — CO por bloco (despesa/receita) deve casar com a classe da conta
- **O que observamos:** CO `1001` (bloco "Despesa") aparece em conta **classe 7**
  (`721900000`, controle). A regra espera CO de despesa só em classes 1, 2, 5, 6.
- **❓ Pergunta:** As classes de controle (7 e 8) **podem** carregar COs do bloco
  Despesa/Receita, ou a restrição por classe está correta?

---

## 4. Saldos em contas patrimoniais

### R040 / R041 — Conta patrimonial deve ter saldo inicial / final
- **O que observamos:** contas como `211110199` (sem saldo inicial) e `113810800`
  (sem saldo final) — cada uma com um único registro, sem a entrada de saldo.
- **❓ Pergunta:** Toda conta patrimonial (classes 1, 2, 5, 6) **precisa
  obrigatoriamente** ter `beginning_balance` e `ending_balance`, ou há casos
  legítimos (conta nova no período, conta que zerou) sem essas entradas?

---

## 5. Remanescente do R020 (IC obrigatório faltante)

- **O que observamos:** após corrigir o R020, restam ~11 contas sem **FR (Fonte
  de Recursos)** obrigatório (ex. `113119900`, `211110102`), e poucas sem DC/FS/ND.
- **❓ Pergunta:** Essas contas realmente deveriam ter FR informado, ou há
  situação em que FR também é dispensado? (Se forem pendências reais, tudo bem —
  99,795% admite um resíduo pequeno.)

---

## Resumo do pedido

Para cada pergunta acima, precisamos do **critério correto** (o que a norma/STN
espera). Com isso, ajustamos cada regra (mantendo as que forem pendência real e
desativando/corrigindo as que forem falso-positivo), até o motor refletir o
resultado oficial de ~99,8% de João Pessoa.
