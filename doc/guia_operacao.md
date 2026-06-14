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
- Dados persistidos: `data/snapshots`, `data/reports`, `data/logs`.

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

Para gerar hash de senha:

```powershell
.\.venv\Scripts\python.exe -c "import bcrypt; print(bcrypt.hashpw(b'senha', bcrypt.gensalt()).decode())"
```

Para gerar secret:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

Em producao, nao use `change-me-in-production`.

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

    make prod-up      # docker compose -f docker-compose.prod.yml up --build -d
    make prod-down    # derruba o stack

### 3. Substituir pelo certificado institucional

Quando a prefeitura fornecer um certificado oficial, basta substituir os dois
arquivos e reiniciar o nginx:

    cp <cert-institucional>.pem  docker/nginx/certs/fullchain.pem
    cp <chave-institucional>.pem docker/nginx/certs/privkey.pem
    docker compose -f docker-compose.prod.yml restart nginx

### 4. Validacao

- `curl -k https://<host>/api/health` -> HTTP 200 com as regras esperadas
- `curl -I http://<host>` -> HTTP 308 redirecionando para https
- login e upload de CSV pela SPA funcionam atraves do proxy

Ajustes:

- Limite de upload (`client_max_body_size`, default `200m`) e timeouts de
  processamento (`proxy_read_timeout`/`proxy_send_timeout`, default `300s`)
  ficam centralizados em `docker/nginx/nginx.conf`.
