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
- Dados persistidos: `data/snapshots`, `data/reports`, `data/logs`, `data/uso`
  (no aplicativo desktop, dentro de `%LOCALAPPDATA%\MCRA\data`).

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

No instalador do aplicativo desktop (`MCRA-Setup-<versao>.exe`) os usuarios
da equipe listados em `config/settings.desktop.yaml` ja vem cadastrados; as
senhas sao entregues pelo responsavel tecnico por um canal separado (nunca no
e-mail com o link do instalador). Quem entra depois recebe um convite (ver a
secao "Convites") e escolhe a propria senha.

Senha esquecida no aplicativo desktop: o caminho e pedir um novo convite ao
responsavel tecnico. O convite para um e-mail que ja tem conta naquele
computador **troca a senha** dessa conta, sem apagar nada (ver "Convites").

Alternativa para versoes do aplicativo sem convite (a tela de login nao tem
"Tenho um convite"): feche o aplicativo e apague
`%LOCALAPPDATA%\MCRA\config\settings.yaml`; no proximo arranque ele recria a
configuracao com as senhas originais, e os dados (snapshots, relatorios, logs)
ficam onde estavam. **Atencao:** isso tambem apaga as contas criadas por
convite naquele computador; elas precisam de um convite novo.

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

## Tempo de uso por usuario

A API mede quanto tempo cada usuario passa no app (aba aberta e uso ativo),
por rota, e guarda isso em `data/uso/`. Cada pessoa ve so o proprio tempo na
tela `/uso`; nao ha consolidado de equipe.

### Os arquivos

- `data/uso/<YYYY-MM>.jsonl` — mes corrente, ainda recebendo escrita. Cada
  linha e um **delta** (incremento de um ciclo de flush), nao um total
  acumulado.
- `data/uso/<YYYY-MM>.agg.jsonl` — mes ja fechado, compactado em uma linha
  por `(usuario, dia, rota)`.

A compactacao roda sozinha, sem intervencao: no primeiro flush de um mes
novo, a API varre os meses anteriores ainda em formato bruto, compacta cada
um e apaga o `.jsonl` bruto correspondente. Um mes fechado nunca mais muda.

### Por que delta e nao total acumulado

Se cada linha guardasse o total do dia, o servidor precisaria lembrar esse
total entre reinicios. Um restart no meio do dia gravaria por cima do que ja
existia e o contador andaria para tras. Com delta, agregar e so somar, e um
restart nunca reduz o tempo ja registrado.

### Janela de perda de dado

O acumulador em memoria e gravado em disco a cada 5 minutos, mais uma vez no
shutdown. Uma queda do processo entre dois flushes perde, no maximo, os
ultimos 5 minutos de uso. Isso e deliberado: e telemetria de uso, nao dado
contabil, e nao vale a complexidade de garantir zero perda.

### Custo em disco

Com 10 usuarios, um mes bruto fica em torno de 3,8 MB; depois da compactacao,
o ano inteiro fica em torno de 2,4 MB. A compactacao existe justamente para
manter esse numero baixo com o historico completo, sem expurgo.

### Como apagar o historico de uma pessoa

Nao existe endpoint para isso — e deliberado, para nao abrir uma rota capaz
de apagar dado de uso de terceiros por engano ou abuso. O procedimento e
manual:

1. Parar a API (ou aceitar que o cache em memoria continua servindo o dado
   antigo ate reiniciar — ver observacao abaixo).
2. Remover as linhas do usuario nos arquivos `data/uso/*.jsonl` e
   `data/uso/*.agg.jsonl` relevantes.
3. **Reiniciar a API.** E obrigatorio: o agregado de mes fechado fica em
   cache dentro do processo, e o cache so e reconstruido a partir do arquivo
   quando o processo sobe de novo. Editar o arquivo sem reiniciar deixa o
   dado removido ainda visivel, servido do cache.

### Suposicao de worker unico

O lock que protege a escrita no JSONL mensal so serializa threads dentro de
**um** processo. Isso e seguro porque `docker/entrypoint.sh` sobe o
`uvicorn` sem a flag `--workers` — hoje existe exatamente um processo da
API. Se algum dia alguem adicionar `--workers` (ou qualquer forma de rodar
mais de um processo da API ao mesmo tempo), esse lock deixa de proteger:
dois processos podem intercalar escritas parciais no mesmo arquivo mensal e
corromper o JSONL. Antes de adicionar `--workers`, e preciso trocar esse
lock por um lock de arquivo de verdade (cross-process).

### Privacidade

O arquivo e texto puro no disco do servidor. Qualquer pessoa com acesso ao
container consegue ler o tempo de uso de todo mundo com um `cat`, mesmo a
interface so mostrando a cada um o proprio numero. Isso nao e uma falha do
desenho — e consequencia direta de guardar historico permanente de dado
pessoal de servidor publico. Trate `data/uso/` com o mesmo cuidado que
`config/settings.yaml` (credenciais): acesso ao servidor implica acesso a
esse dado.

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

---

## Convites

O convite assinado deixa o responsavel tecnico (o "emissor") chamar um
colaborador por e-mail, sem criar a conta a mao: o colaborador recebe o link do
instalador e um codigo, instala o MCRA, cola o codigo na tela de entrada e
escolhe a propria senha. Nao ha servidor: o codigo e assinado com uma chave que
so o emissor tem, e cada computador confere a assinatura com a chave publica
embutida no instalador.

**O recurso fica desligado enquanto `public_key` estiver vazio em
`config/invites.yaml`.** Desligado, nao aparecem "Tenho um convite" na tela de
entrada nem "Convidar" no menu. A chave publica so e preenchida pela cerimonia
abaixo.

O que fica onde:

| O que | Onde | Segredo? |
|---|---|---|
| Chave publica, link do instalador, validade | `config/invites.yaml` (versionado e embutido no instalador) | nao |
| Chave privada (o arquivo guarda a chave cifrada com a senha da chave) | `invite_key.pem`, na pasta de config local | sim |
| Emissor, conta do Gmail e senha de app (cifrada) | `invite_issuer.yaml`, na pasta de config local | sim |
| Convites emitidos (sem o codigo) | `invites_sent.jsonl`, na pasta de config local | nao |
| Convites ja usados neste computador | `invites_used.json`, na pasta de config local | nao |

A pasta de config local e a do `settings.yaml` em uso. No aplicativo desktop e
`%LOCALAPPDATA%\MCRA\config`.

**Cuidado ao desinstalar o MCRA:** o desinstalador pergunta se deve apagar os
dados do usuario (`%LOCALAPPDATA%\MCRA`). Responder "Sim" apaga tambem o
`invite_key.pem` e o `invite_issuer.yaml`. Antes de desinstalar no computador do
emissor, guarde a copia dos dois arquivos (passo 5 da cerimonia abaixo) e, depois
de reinstalar, devolva os dois a `%LOCALAPPDATA%\MCRA\config`. So a chave nao
basta: sem o `invite_issuer.yaml` o item "Convidar" nao aparece, e recria-lo
exige `init --force`, que troca a chave.

### Cerimonia do emissor (uma vez)

Rode no PowerShell, da raiz do clone do repositorio, com o ambiente virtual do
projeto (ative com `.\.venv\Scripts\Activate.ps1` ou troque `python` por
`.\.venv\Scripts\python.exe`):

1. Gere a chave e grave o emissor:

   ```powershell
   python scripts/setup_invites.py init --issuer <e-mail> --smtp-user <conta do Gmail>
   ```

   - `<e-mail>` e o login do emissor no MCRA (o e-mail de quem vai convidar);
   - `<conta do Gmail>` e a conta que envia os convites.

   O comando pede, sem eco: a **senha da chave** (duas vezes, 12 caracteres ou
   mais) e a **senha de app do Gmail** (uma senha propria para aplicativos,
   gerada na conta do Google; nao e a senha normal do Gmail). Depois grava:
   a chave privada cifrada (`invite_key.pem`) e o `invite_issuer.yaml` em
   `%LOCALAPPDATA%\MCRA\config`, e a chave publica em `config/invites.yaml`.
   Nenhum segredo e impresso na tela.
2. Faca o commit do `config/invites.yaml` (so a chave publica mudou) e o merge.
3. Rode o workflow `Release desktop` e ponha o instalador novo na pasta do
   Drive (o link da pasta esta em `installer_url`).
4. Instale a versao nova no computador do emissor. Entrando com o e-mail do
   passo 1, o item **Convidar** aparece no menu.
5. Guarde uma copia do `invite_key.pem` e do `invite_issuer.yaml` num lugar
   seguro (os dois ficam em `%LOCALAPPDATA%\MCRA\config`). Sem eles (ou sem a
   senha da chave) nao ha como emitir convites: ver "Perdeu a chave" abaixo.

Se o e-mail do emissor ainda nao tem conta no MCRA instalado, o `init` avisa e
o item "Convidar" nao aparece. Crie a conta (este comando tambem serve de
"esqueci a senha" do proprio emissor, que nao tem a quem pedir convite):

```powershell
python scripts/create_user.py --username <e-mail> --config "$env:LOCALAPPDATA\MCRA\config\settings.yaml"
```

A senha e pedida no prompt, sem eco.

**Use o e-mail EXATAMENTE como esta gravado no `settings.yaml`, com as mesmas
maiusculas e minusculas.** O comando compara o nome cru: com outra caixa ele nao
acha a conta existente, cria uma segunda conta e a senha antiga continua
valendo na primeira.

### Qual pasta de config o script usa

Por padrao o `setup_invites.py` grava em `%LOCALAPPDATA%\MCRA\config`, a pasta
do aplicativo instalado. A API de desenvolvimento (`uvicorn`, ver "Subir em
desenvolvimento") le a `config/` do clone: sao pastas diferentes. Quem testa o
convite pela API de desenvolvimento precisa apontar o script para a pasta do
`settings.yaml` que a API usa:

```powershell
python scripts/setup_invites.py init --issuer <e-mail> --smtp-user <conta do Gmail> --state-dir config
```

`--state-dir` escolhe a pasta; o `create_user.py` correspondente usa `--config
config\settings.yaml` (o padrao dele).

### Convidar alguem

1. Entre no MCRA com o login do emissor e abra **Convidar** no menu.
2. Informe o **e-mail do colaborador** e a **senha da chave** e clique em
   **Enviar convite**.
3. O MCRA envia o e-mail (link do instalador, codigo e validade) e mostra
   "Convite enviado por e-mail" com a data de vencimento.
4. Se o e-mail nao sair (Gmail recusou a senha de app, sem internet), a tela
   avisa "O e-mail nao saiu" e mostra o codigo para copiar. O convite continua
   valido: envie o codigo ao colaborador por outro meio.
5. A tabela "Convites emitidos neste computador" lista o que ja foi emitido
   (sem o codigo).

O colaborador instala o MCRA, clica em **Tenho um convite** na tela de entrada,
cola o codigo e escolhe a senha (8 a 72 caracteres). Se o e-mail dele ja tem
conta naquele computador, o convite **troca a senha** dessa conta: e assim que
se atende "esqueci a senha".

### Trocar o link do Drive

O link do instalador fica so no `config/invites.yaml`. Para trocar:

```powershell
python scripts/setup_invites.py set-url <link>
```

O `set-url` so aceita link que comece com `https://`.

Depois faca o commit, um release novo e instale-o no computador do emissor: o
link e lido do `invites.yaml` embutido no instalador, e quem monta o e-mail e o
MCRA do emissor. Convites ja enviados continuam com o link antigo.

### Instalador no Drive (envio automatico, opcional)

O workflow `Release desktop` tem um passo que envia o instalador para a pasta
do Drive, sempre com o nome `MCRA-Setup.exe` (o arquivo anterior e substituido,
entao o link da pasta nao muda). O passo fica **desligado** ate a configuracao
abaixo existir, e nunca derruba o release: se o envio falhar, o instalador
continua como artefato do Actions e pode ser copiado a mao, como hoje.

**Ainda nao foi testado de ponta a ponta**: na primeira vez, confira na pasta
do Drive se o arquivo chegou.

Configuracao, uma vez, por quem administra a conta Google dona da pasta (ou com
permissao de edicao nela):

1. No Google Cloud Console, crie um projeto, ative a **Google Drive API** e crie
   uma credencial OAuth do tipo "App para computador". Na tela de consentimento,
   publique o app ("Em producao"): em modo de teste a autorizacao vence em uma
   semana. O rclone exige credencial propria; a compartilhada dele esta sendo
   desativada em 2026.
2. Num computador com navegador e o rclone instalado, logado na conta Google da
   pasta:

   ```powershell
   rclone authorize "drive" "<client_id>" "<client_secret>"
   ```

   Copie o JSON que ele imprime (o token).
3. No GitHub, em Settings > Secrets and variables > Actions, crie:
   - segredos `GDRIVE_CLIENT_ID`, `GDRIVE_CLIENT_SECRET` e `GDRIVE_TOKEN` (o
     JSON do passo 2);
   - variavel `GDRIVE_FOLDER_ID` com o ID da pasta (o trecho depois de
     `/folders/` no link do Drive).
4. Rode o `Release desktop` e confira o passo "Publicar o instalador no Drive".

O acesso pedido ao Drive e o completo da conta autorizada (a pasta foi criada
a mao, e o escopo restrito so enxerga arquivos criados pelo proprio rclone). Por
isso, prefira uma conta Google dedicada ao MCRA, com permissao de edicao so
nessa pasta. O rclone e instalado no runner pelo Chocolatey, um pacote mantido
por terceiros.

### Perdeu a chave ou a senha da chave

Nao ha recuperacao. Repita a cerimonia do passo 1 com `--force`:

```powershell
python scripts/setup_invites.py init --issuer <e-mail> --smtp-user <conta do Gmail> --force
```

Isso gera uma chave nova e exige commit, merge e um release novo. **Os convites
ja emitidos deixam de valer**; as contas ja criadas continuam funcionando. Sem
`--force` o comando recusa sobrescrever a chave existente.

Dois avisos:

- **Entre rodar `init --force` e instalar a versao nova no computador do emissor,
  NAO convide ninguem.** Nesse intervalo a chave local (a nova) nao e a da versao
  instalada, e o app recusa o envio com uma mensagem. Conclua commit, merge,
  release e instalacao antes de voltar a convidar.
- **Quem tem uma versao antiga instalada precisa instalar a versao nova** para
  aceitar convites assinados pela chave nova. Isso vale tambem para o "esqueci a
  senha": a versao antiga confere a assinatura com a chave publica antiga e
  recusa o codigo novo.

### Limites

- **Nao ha revogacao antes do vencimento.** Um convite emitido vale ate vencer
  (o prazo de `validity_days`); para anular um convite antes, so trocando a chave
  (convites antigos deixam de valer, ver acima).
- **O uso unico vale por computador.** O mesmo codigo nao funciona duas vezes no
  mesmo computador, mas pode ser usado uma vez em cada computador onde o MCRA
  esteja instalado.
