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
- Dados persistidos: `data/snapshots`, `data/reports`, `data/logs`, `data/uso`.

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

Para criar o primeiro usuario nao ha passo manual de hash. Tres caminhos:

1. **Navegador (recomendado)**: com o app no ar e nenhum usuario configurado,
   a tela de login vira "Primeiro acesso" e cria o administrador ali mesmo.
   O endpoint (`POST /api/auth/setup`) tranca assim que existe um usuario.
2. **CLI** (tambem para usuarios adicionais/troca de senha):

```powershell
.\.venv\Scripts\python.exe scripts\create_user.py --username admin
# a senha e pedida no prompt, sem eco
```

3. **Docker**: defina `RANKING_MSC_ADMIN_USERNAME` e `RANKING_MSC_ADMIN_PASSWORD`
   no ambiente do compose: o `entrypoint.sh` cadastra o usuario no primeiro boot.

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

O servidor da prefeitura pode nao ter saida liberada para a internet. Antes
de depender da tela **Entregas** em producao, valide a conectividade direto
do servidor:

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

## Subir build unificado sem Docker

Gerar build do frontend:

```powershell
cd web
npm.cmd run build
cd ..
```

Subir FastAPI servindo API e SPA:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000
```

Acesse `http://localhost:8000`.

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
| `/api/health` nao responde | Backend parado ou porta errada | Reiniciar uvicorn e verificar porta. |
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

Diretorios a preservar:

- `config/settings.yaml`;
- `data/snapshots`;
- `data/reports`;
- `data/logs`;
- `data/uso`;
- `ref`.

Recomendacao minima:

- backup diario de `data`;
- backup sempre antes de atualizar versao;
- manter snapshots mensais usados em comparacoes e auditorias.

---

## Atualizacao de versao

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

## Publicacao com reverse proxy (nginx + TLS)

Em producao, o MCRA roda atras de um reverse proxy nginx que termina TLS e
encaminha o trafego para o container do app. O app deixa de ser exposto
diretamente na porta `8000` do host — so o nginx publica as portas `80` e `443`.

Topologia:

    Cliente  HTTPS :443 -> [nginx] -> (rede interna) -> [app:8000]
             HTTP  :80  -> redireciona 308 para :443

### 1. Gerar o certificado

Para subir imediatamente com um certificado self-signed:

    make gen-cert

Isso cria `docker/nginx/certs/fullchain.pem` e `privkey.pem`. O alvo nao
sobrescreve um certificado ja existente. Para definir o nome do host no
certificado, use `make gen-cert CERT_CN=mcra.prefeitura.gov.br`.

### 2. Subir o stack de producao

    make prod-up      # gera o cert se faltar (gen-cert) e sobe o stack
    make prod-down    # derruba o stack

Use sempre `make prod-up`: ele depende de `gen-cert`, entao garante os
certificados antes de o nginx subir. Se precisar usar o `docker compose`
diretamente (sem make), gere ou instale os certificados ANTES, senao o nginx
encerra no startup por falta de `fullchain.pem`/`privkey.pem`:

    make gen-cert     # ou copie os certificados para docker/nginx/certs/
    docker compose -f docker-compose.prod.yml up --build -d

### 3. Substituir pelo certificado institucional

Quando a prefeitura fornecer um certificado oficial (ou para configurar
renovacao automatica via Let's Encrypt), veja a secao "Certificado TLS
valido" mais abaixo — inclui os comandos e as permissoes corretas. Nao use
`restart nginx` para trocar o certificado: ele derruba conexoes em
andamento; a secao referida usa `nginx -s reload`, que e gracioso.

### 4. Validacao

- `curl -k https://<host>/api/health` -> HTTP 200 com as regras esperadas
- `curl -I http://<host>` -> HTTP 308 redirecionando para https
- login e upload de CSV pela SPA funcionam atraves do proxy

Ajustes:

- Limite de upload (`client_max_body_size`, default `200m`) e timeouts de
  processamento (`proxy_read_timeout`/`proxy_send_timeout`, default `300s`)
  ficam centralizados em `docker/nginx/nginx.conf`.

## Certificado TLS valido

O self-signed serve para desenvolvimento. Em qualquer ambiente acessado por
outra pessoa, use certificado emitido por autoridade reconhecida — caso
contrario o navegador exibe aviso de conexao nao privada.

O nginx le sempre os mesmos dois arquivos:

- `docker/nginx/certs/fullchain.pem`
- `docker/nginx/certs/privkey.pem`

Qualquer origem de certificado funciona, desde que produza esses dois arquivos.

### Opcao A — certificado institucional (PMJP)

Copie os dois arquivos fornecidos pela TI para `docker/nginx/certs/`, ajuste
as permissoes e recarregue:

```bash
cp <cert-institucional>.pem  docker/nginx/certs/fullchain.pem
cp <chave-institucional>.pem docker/nginx/certs/privkey.pem
chmod 644 docker/nginx/certs/fullchain.pem
chmod 600 docker/nginx/certs/privkey.pem
docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

`cp` como root herda o modo do arquivo de origem, entao os `chmod` acima nao
sao opcionais — sem eles a chave privada pode ficar com permissao mais aberta
do que `600`.

### Opcao B — Let's Encrypt (gratuito, renovacao automatica)

Requer dominio publico apontando para o servidor e a porta 80 acessivel.

O Let's Encrypt limita 5 falhas por hora por dominio — confirme que a porta
80 esta alcancavel de fora ANTES de rodar o certbot, para nao gastar essas
tentativas a toa.

O teste so faz sentido com o stack **ja no ar**, porque quem responde na porta
80 e o nginx do proprio stack. Se ainda nao subiu, rode antes:

```bash
make gen-cert   # self-signed temporario, so para o nginx conseguir subir
make prod-up
```

Com o stack no ar, teste de uma maquina fora do servidor:

```bash
curl -sI http://SEU.DOMINIO | head -1   # deve devolver 308
```

Nao prossiga sem essa resposta. Como diagnosticar o que veio:

| Resposta | Causa provavel |
|---|---|
| `308` | tudo certo, siga para o certbot |
| conexao recusada | o stack nao esta no ar — rode `make prod-up` |
| conexao pendura / timeout | firewall do host (ufw/iptables) ou do provedor (regra de seguranca na nuvem) |
| responde outro servico | outra coisa ja ocupa a porta 80 no servidor |

```bash
sudo apt install certbot
sudo RANKING_MSC_REPO_DIR=/caminho/do/repo certbot certonly --webroot \
  -w /caminho/do/repo/docker/nginx/certbot-webroot \
  -d SEU.DOMINIO \
  --deploy-hook /caminho/do/repo/scripts/deploy/renew-hook.sh
```

O `renew-hook.sh` publica os PEMs em `docker/nginx/certs/` e recarrega o nginx.
A renovacao automatica ja vem no systemd timer instalado com o pacote certbot.

O `RANKING_MSC_REPO_DIR` acima e usado apenas na emissao manual. O certbot
persiste `renew_hook = <script>` em
`/etc/letsencrypt/renewal/SEU.DOMINIO.conf`, mas NAO persiste variaveis de
ambiente — o timer systemd roda `certbot -q renew` com ambiente limpo. Por
isso o hook deriva a raiz do repositorio sozinho, a partir do proprio
caminho (`<repo>/scripts/deploy/renew-hook.sh`), sem depender de
`RANKING_MSC_REPO_DIR` estar definida na renovacao automatica. A variavel
serve como override explicito, so necessario se o script for instalado fora
do layout padrao do repo (copiado/symlinkado para outro caminho).

O nginx precisa estar no ar antes da emissao, para servir o desafio na porta 80.
Na primeira vez: `make gen-cert` (self-signed, so para o nginx subir),
`make prod-up`, e entao o certbot substitui pelo valido.

Valide a renovacao antes de confiar nela. `certbot renew --dry-run` valida
APENAS o desafio ACME (prova que o dominio e alcancavel e o certbot consegue
emitir) -- ele PULA o deploy hook (log "Dry run: skipping deploy hook
command"), entao nao prova que o hook publica o certificado nem que o nginx
recarrega. O flag `--run-deploy-hooks` resolveria isso, mas so existe no
certbot 2.8+; o `apt install certbot` do Ubuntu 22.04 entrega 1.21. A prova
real e invocar o hook diretamente:

```bash
sudo RANKING_MSC_REPO_DIR=/caminho/do/repo certbot renew --dry-run

sudo RANKING_MSC_REPO_DIR=/caminho/do/repo \
  RENEWED_LINEAGE=/etc/letsencrypt/live/SEU.DOMINIO \
  /caminho/do/repo/scripts/deploy/renew-hook.sh
ls -l docker/nginx/certs/    # mtime deve ser de agora
```
