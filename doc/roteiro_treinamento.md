# Roteiro de Treinamento e Demonstracao - Ranking MSC

> Publico: equipe contabil, controladoria e usuarios internos que validam a MSC.
> Duracao estimada: 30 a 40 minutos (demonstracao guiada + duvidas).
> Tarefa de backlog: F5-10.

---

## Objetivo

Capacitar a equipe usuaria a operar o Ranking MSC de ponta a ponta sem apoio
paralelo: enviar a MSC mensal, ler o score, tratar pendencias e gerar os
relatorios para a correcao antes do fechamento.

Documentos de apoio: `doc/manual_usuario.md` (fluxo de uso) e
`doc/guia_operacao.md` (operacao, backup e troubleshooting).

---

## Pre-requisitos

- Aplicativo instalado na maquina de cada participante (instalador MCRA-Setup).
- O e-mail e a senha de cada pessoa, entregues pelo responsavel tecnico.
- Um CSV MSC de exemplo de uma competencia real, autorizado para demonstracao.
- Projetor ou tela compartilhada.

Antes de comecar, abrir o aplicativo numa das maquinas e confirmar que a tela de
login aparece. Depois do login, abrir a tela `Regras` e conferir o cabecalho
"78 regras registradas".

---

## Roteiro da demonstracao

Apresentar cada etapa fazendo ao vivo e explicando o "porque", nao so o "como".

### 1. Acesso e login (3 min)
- Abrir o aplicativo pelo atalho do menu iniciar.
- Explicar que o acesso e por e-mail e senha, com sessao que expira.
- Mostrar onde aparece o usuario logado e o botao `Sair`.
- Dizer onde ficam os dados: `%LOCALAPPDATA%\MCRA`. Cada pessoa tem os seus.

### 2. Upload e execucao (5 min)
- Em `Inicio`, enviar o CSV MSC de exemplo.
- Explicar o formato esperado do arquivo (ver `doc/manual_usuario.md`, secao
  "Arquivo MSC esperado").
- Mostrar o resumo da execucao: competencia, regras executadas e tempo.
- Reforcar: um mesmo ente + competencia nao processa em paralelo (lock).

### 3. Score e banda (5 min)
- Apresentar a nota (0-100) e a banda (A-E).
- Abrir o detalhamento por dimensao (Estrutura, Fechamento, IC/Dominio,
  PCASP/Completude, Temporal) e explicar o peso de cada uma.
- Referenciar `doc/modelo_pontuacao.md` para quem quiser o detalhe da formula.

### 4. Pendencias (8 min)
- Mostrar a lista de pendencias e os filtros por severidade, regra e conta.
- Explicar a diferenca entre ERRO e ALERTA.
- Clicar numa linha para abrir o detalhe da regra e da conta.
- Usar a paginacao para mostrar que todas as pendencias ficam acessiveis na tela.

### 5. Catalogo de regras (3 min)
- Abrir `Regras` e mostrar a lista das 78 regras com dimensao e descricao.
- Demonstrar como localizar uma regra especifica a partir de uma pendencia.

### 6. Exportacoes (4 min)
- Gerar o Excel de pendencias (lista completa para trabalho offline).
- Gerar o PDF executivo (visao de uma pagina para gestao).
- Indicar onde os arquivos sao salvos (ver `doc/guia_operacao.md`, "Saidas geradas").

### 7. Superavit por FR (4 min)
- Abrir a tela de Superavit e explicar a leitura por fonte de recurso.
- Observacao: a validacao contabil final desta derivacao com dados reais da
  PMJP e a tarefa GO-02 (em andamento com a area contabil).

### 8. Comparar competencias (3 min)
- Demonstrar a comparacao entre dois meses (evolucao de score e pendencias).
- Explicar o uso para acompanhamento mensal e auditoria.

### 9. Encerramento da sessao (1 min)
- Fazer logout e mostrar que rotas protegidas deixam de abrir apos sair.

---

## Mensagens-chave a transmitir

- O sistema apoia a correcao **antes** do envio/fechamento; nao substitui o
  julgamento contabil.
- ERRO indica inconsistencia que normalmente bloqueia; ALERTA pede analise.
- O Excel traz a pendencia completa; o PDF traz a visao executiva.
- Em caso de duvida ou erro, consultar `doc/manual_usuario.md` (secao
  "Problemas comuns") e os contatos de suporte do handoff.

---

## Coleta de duvidas e ajustes

- Reservar os ultimos minutos para perguntas.
- Registrar duvidas recorrentes e eventuais ajustes finais realmente
  necessarios (texto/mensagem/usabilidade) como itens de backlog.
- Ajustes de escopo maior entram nas decisoes TECH-02/03/04, nao no go-live.

---

## Checklist do facilitador

- [ ] Aplicativo instalado e tela de login testada em pelo menos uma maquina, com "78 regras registradas" na tela `Regras` apos o login
- [ ] E-mail e senha de demonstracao testados antes da sessao
- [ ] CSV MSC de exemplo carregado e validado
- [ ] Excel e PDF gerando sem erro
- [ ] Manual e guia de operacao acessiveis aos participantes
- [ ] Duvidas e ajustes registrados ao final
