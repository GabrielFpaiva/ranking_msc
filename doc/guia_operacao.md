# Guia de Operacao - Ranking MSC

> Publico: TI, sustentacao e responsaveis pela operacao local.

---

## Objetivo

Este guia descreve como preparar ambiente, subir a aplicacao, validar saude,
executar checks, revisar logs e operar os arquivos gerados pelo Ranking MSC.

---

## Componentes

- Backend: FastAPI em `app/api`.
- Motor: pacote Python em `src/ranking_msc`.
- Frontend: React/Vite em `web`.
- Configuracao: `config/settings.yaml`.
- Referencias: `ref`.
- Dados persistidos: `data/snapshots`, `data/reports`, `data/logs` (no
  aplicativo desktop, dentro de `%LOCALAPPDATA%\MCRA\data`).

---

## Preparacao local no Windows

Criar ambiente Python:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Instalar dependencias do frontend:

```powershell
cd web
npm.cmd install
cd ..
```
Se o PowerShell bloquear `npm`, use `npm.cmd`.

---

## Configuracao

O arquivo operacional e `config/settings.yaml`.

Campos criticos:

- `paths.snapshots_dir`: onde ficam snapshots Parquet;
- `paths.reports_dir`: onde ficam Excel/PDF;
- `paths.logs_dir`: onde fica o log JSONL;
- `paths.ref_dir`: tabelas de referencia;
- `rules.enabled`: regras executadas;
- `security.secret_key`: chave JWT;
- `security.users`: usuarios e hashes bcrypt.

No instalador do aplicativo desktop (`MCRA-Setup-<versao>.exe`) os tres
usuarios da equipe ja vem cadastrados; as senhas sao entregues pessoalmente
pelo responsavel tecnico. Senha esquecida no aplicativo desktop: feche o
aplicativo e apague `%LOCALAPPDATA%\MCRA\config\settings.yaml`; no proximo
arranque ele recria a configuracao com as senhas originais, e os dados
(snapshots, relatorios, logs) ficam onde estavam.

O que segue vale para quem roda a API fora do
instalador (desenvolvimento local), onde nao ha passo manual de hash:

1. **Navegador (recomendado)**: com o app no ar e nenhum usuario configurado,
   a tela de login vira "Primeiro acesso" e cria o administrador ali mesmo.
   O endpoint (`POST /api/auth/setup`) tranca assim que existe um usuario.
2. **CLI** (tambem para usuarios adicionais/troca de senha):

```powershell
.\.venv\Scripts\python.exe scripts\create_user.py --username admin
# a senha e pedida no prompt, sem eco
```

O caminho via variaveis de ambiente e Docker Compose foi aposentado em
21/09/2026 junto com o material em `doc/legacy/`.

Em todos os caminhos o hash bcrypt e um `secret_key` seguro sao gerados
automaticamente (o placeholder `change-me-in-production` e substituido).

Nao e preciso reiniciar a API depois de criar/alterar usuarios: o servidor
detecta mudancas no `settings.yaml` (mtime) e recarrega a configuracao na
requisicao seguinte.

### Bloco `siconfi`

Configura a consulta ao extrato de entregas do Siconfi, usada pela tela
**Entregas** (Dimensao I do Ranking):

```yaml
siconfi:
  id_ente: 2507507              # codigo IBGE do ente (Joao Pessoa - PB)
  cache_ttl_horas: 24
  prazos_dias:
    "Relatório Resumido de Execução Orçamentária": 30
    "Relatório de Gestão Fiscal": 30
```

- `id_ente`: codigo IBGE do ente consultado na API do Tesouro. Nao alterar sem
  confirmar o codigo correto do municipio.
- `cache_ttl_horas`: por quantas horas uma resposta da API fica valida em
  cache antes de a tela buscar de novo. Enquanto o cache estiver dentro do
  TTL, a tela serve do cache sem chamar a API — isso e o caminho normal, nao
  degradacao.
- `prazos_dias`: mapa `nome do entregavel -> prazo em dias apos o fim do
  periodo`. **Entregavel ausente deste mapa aparece na tela sem veredicto de
  atraso** — so o dado factual (dias decorridos desde o fim do periodo), sem
  o rotulo "no prazo"/"fora do prazo". Essa e uma decisao consciente do
  projeto: DCA, MSC Agregada e MSC Encerramento ficam de fora de proposito,
  porque ainda nao ha fundamentacao normativa confirmada para os prazos
  desses tres entregaveis. Nao adicione esses entregaveis ao mapa sem
  confirmar o prazo com a contabilidade.

  Os dois prazos ja configurados por padrao tem fundamento em norma: RREO
  (Relatorio Resumido de Execucao Orcamentaria) e RGF (Relatorio de Gestao
  Fiscal), 30 dias cada, conforme LRF (Lei de Responsabilidade Fiscal,
  LC 101/2000) arts. 52 e 55 par. 2.

### Teste de conectividade com o Siconfi

A maquina onde o MCRA esta instalado pode nao ter saida liberada para a
internet. Antes de depender da tela **Entregas**, valide a conectividade
direto dela:

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/entes?id_ente=2507507"
```

- `200`: a consulta funciona, a tela busca dados atuais da API.
- Qualquer outro resultado (timeout, erro de DNS, codigo diferente de `200`):
  indica bloqueio de firewall/proxy. A tela continua funcionando em modo
  cache (ultimo dado salvo), mas nao atualiza ate a saida para a internet ser
  liberada. Nesse cenario, verifique liberacao de saida para
  `apidatalake.tesouro.gov.br` (HTTPS/443) com o time de rede da prefeitura.

---

## Subir em desenvolvimento

Backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd web
npm.cmd run dev -- --host 127.0.0.1
```

URLs:

- frontend: `http://127.0.0.1:5173`;
- backend: `http://127.0.0.1:8000`;
- healthcheck: `http://127.0.0.1:8000/api/health`.

---

## Subir build unificado localmente

Uso principal: conferir o build completo (SPA + API) antes de empacotar. O
empacotamento para distribuicao usa `make desktop-build` (ver secao
"Distribuicao do aplicativo desktop").

Gerar build do frontend:

```powershell
cd web
npm.cmd run build
cd ..
```

Subir FastAPI servindo API e SPA:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

Acesse `http://127.0.0.1:8000`.

---

## Validacao

Checks Python:

```powershell
.\.venv\Scripts\python.exe -m ruff check src/ tests/ app/
.\.venv\Scripts\python.exe -m mypy src/ app/api/
.\.venv\Scripts\python.exe -m pytest --basetemp .codex_pytest_tmp -p no:cacheprovider --cov=ranking_msc --cov-report=term-missing --cov-fail-under=80
```

Observacao Windows/sandbox: use `--basetemp .codex_pytest_tmp` para evitar que
o pytest tente criar temporarios em um diretorio sem permissao.

Checks frontend:

```powershell
cd web
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run build
cd ..
```

---

## Smoke test da API

Healthcheck:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/health
```

Login:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/auth/token `
  -ContentType "application/x-www-form-urlencoded" `
  -Body "username=admin&password=admin&grant_type=password"
```

Para validar fluxo completo, use uma MSC de `ref/amostras` pela interface ou
por cliente HTTP autenticado.

---

## Saidas geradas

Snapshots:

```text
data/snapshots/<siconfi>/<competencia>/msc_normalizado.parquet
data/snapshots/<siconfi>/<competencia>/resultado_regras.parquet
data/snapshots/<siconfi>/<competencia>/scoring_metadata.json
```

Relatorios:

```text
data/reports/pendencias_<siconfi>_<competencia>.xlsx
data/reports/executivo_<siconfi>_<competencia>.pdf
```

Logs:

```text
data/logs/ranking_msc.jsonl
```

---

## Concorrencia

O endpoint `/api/run` usa lock por `siconfi + competencia`.

Objetivo:

- evitar duas execucoes simultaneas escrevendo os mesmos snapshots;
- evitar sobrescrita do Excel deterministico da competencia;
- devolver HTTP `409` quando uma execucao equivalente ja esta em andamento.

Locks temporarios ficam em:

```text
data/snapshots/.locks/
```

Em operacao normal, o lock e removido ao final da execucao. Se houver queda
abrupta do processo, um arquivo `.lock` pode permanecer. Antes de remover um
lock manualmente, confirme que nao existe execucao ativa para o mesmo
SICONFI/competencia.

---

## Rotina operacional

### Inicio do dia

1. Confirmar que a aplicacao responde em `/api/health`.
2. Conferir espaco em disco de `data`.
3. Conferir logs recentes em `data/logs/ranking_msc.jsonl`.
4. Fazer login e abrir a tela **Inicio**.

### Depois de cada processamento

1. Confirmar status da execucao.
2. Confirmar que snapshots foram criados.
3. Confirmar que Excel foi criado.
4. Se necessario, gerar PDF executivo.

### Fechamento mensal

1. Processar a competencia atual.
2. Processar ou confirmar competencias anteriores usadas na comparacao.
3. Exportar Excel de pendencias.
4. Exportar PDF executivo.
5. Registrar versao do sistema/commit usado.

---

## Troubleshooting

| Sintoma | Causa provavel | Acao |
|---|---|---|
| `/api/health` nao responde (dev local) | Backend parado ou porta errada | Reiniciar uvicorn e verificar porta. |
| Aplicativo desktop nao abre | Falha no arranque (WebView2, porta local ocupada, config corrompida) | Conferir `%LOCALAPPDATA%\MCRA\data\logs\desktop.log`. |
| Login retorna 401 | Usuario/senha incorretos ou hash errado | Revisar `security.users`. |
| Login impossivel para todos | `users` vazio com secret configurado | Cadastrar ao menos um usuario. |
| Upload retorna 400 | CSV vazio ou formato invalido | Validar metadata/cabecalho/separador. |
| Upload retorna 409 | Mesma competencia em execucao | Aguardar ou verificar lock residual. |
| Export Excel retorna 404 | Pipeline nao rodou para a competencia | Executar `/api/run`. |
| PDF retorna 404/422 | Snapshot ausente ou corrompido | Reprocessar MSC. |
| Comparar sem dados | Faltam snapshots historicos | Processar competencias anteriores. |
| Erro de encoding no console Windows | Saida com caracteres Unicode | Usar terminal UTF-8 ou `PYTHONIOENCODING=utf-8`. |

---

## Backup e retencao

O que copiar, em cada maquina onde o MCRA esta instalado:

    %LOCALAPPDATA%\MCRA

Essa pasta contem a configuracao (com os usuarios) e todos os dados gerados:
snapshots por competencia, relatorios e logs. A pasta de instalacao em Arquivos
de Programas nao precisa de backup: ela e recriada pelo instalador.

Como cada pessoa guarda os proprios dados, nao existe copia central. Se a
Controladoria precisar de trilha de auditoria consolidada, os relatorios
precisam ser exportados para uma pasta de rede depois de cada fechamento.

---

## Atualizacao de versao

Este procedimento atualiza um checkout do codigo-fonte, usado em
desenvolvimento e manutencao. Para atualizar o aplicativo instalado nas
maquinas da equipe, veja a secao "Distribuicao do aplicativo desktop".

1. Parar o servidor.
2. Fazer backup de `config` e `data`.
3. Atualizar o repositorio.
4. Instalar dependencias, se necessario.
5. Rodar validacoes.
6. Subir backend/frontend.
7. Rodar smoke test.

Comandos basicos:

```powershell
git pull
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
cd web
npm.cmd install
npm.cmd run build
cd ..
```

## Distribuicao do aplicativo desktop

Ate 21/09/2026 o MCRA era publicado em servidor, atras de um reverse proxy
nginx com TLS (certificado self-signed ou institucional, com opcao de
renovacao automatica via Let's Encrypt). Essa topologia foi aposentada nessa
data: a prefeitura nao provisionou servidor, dominio nem certificado
institucional, e a entrega passou a ser um instalador Windows por maquina,
sem topologia de servidor. O material antigo (compose, Dockerfile, config de
nginx, script de renovacao de certificado e a suite E2E que dependia do
stack) fica preservado em `doc/legacy/`, caso a decisao seja revista.

### Como o instalador e gerado

O workflow `Release desktop` do GitHub Actions builda o instalador Windows
(`MCRA-Setup-<versao>.exe`) a partir de uma tag `v*` (ou disparo manual) e o
anexa como artefato da execucao (`upload-artifact`), para baixar na aba
Actions; o workflow nao cria Release no GitHub. O instalador:

- instala o aplicativo em Arquivos de Programas;
- cria atalho no menu iniciar e na area de trabalho;
- verifica o Edge WebView2 e instala se estiver faltando;
- ao desinstalar, pergunta se deve apagar `%LOCALAPPDATA%\MCRA` (padrao "Nao"),
  explicando o que se perde.

Para empacotar localmente (sem passar pelo CI): `make desktop-build`. Para
rodar o app desktop em desenvolvimento, sem gerar instalador: `make
desktop-run`. Os dois alvos exigem antes `pip install -e ".[desktop]"`
(pywebview e PyInstaller ficam fora do `.[dev]`).

### Assinatura de codigo

O executavel nao e assinado. O Windows SmartScreen mostra aviso na primeira
execucao, e o antivirus corporativo pode bloquear o instalador ou o
executavel. Isso precisa ser testado numa maquina real da prefeitura antes de
qualquer treinamento ou distribuicao ampla. Certificado de assinatura e
decisao pendente do responsavel pelo projeto (compra).
