#!/bin/sh
# Deploy-hook do certbot: publica o certificado renovado no diretorio lido
# pelo nginx e recarrega o servidor sem derrubar conexoes.
#
# O certbot mantem /etc/letsencrypt/live/<dominio>/*.pem como symlinks para
# ../../archive/. Copiamos com -L (dereferencia) porque um bind mount parcial
# de live/ levaria symlinks quebrados para dentro do container.
#
# Variaveis de ambiente:
#   RANKING_MSC_REPO_DIR        raiz do repositorio (opcional; override -- ver abaixo)
#   RENEWED_LINEAGE             definida pelo certbot: /etc/letsencrypt/live/<dominio>
#   DOCKER_COMPOSE_BIN          binario do compose (opcional; default "docker")
#   DOCKER_COMPOSE_SUBCMD       subcomando (opcional; default "compose"; "" para standalone v1)
set -eu

# Fechar janela de permissao: umask evita que privkey fique legivel ao grupo/outros
# entre o cp e o chmod.
umask 077

# O certbot persiste "renew_hook = <script>" em
# /etc/letsencrypt/renewal/<dominio>.conf, mas NAO persiste ambiente: o timer
# systemd roda "certbot -q renew" com ambiente limpo, entao qualquer guarda
# baseada em variavel obrigatoria aborta toda renovacao automatica. Por isso
# derivamos a raiz do repositorio a partir do proprio caminho do script --
# ele mora em <repo>/scripts/deploy/, entao subir dois niveis chega na raiz.
# RANKING_MSC_REPO_DIR continua valendo como override explicito, para quando
# o script for copiado/symlinkado para fora do layout padrao do repo.
if [ -n "${RANKING_MSC_REPO_DIR:-}" ]; then
  REPO_DIR="$RANKING_MSC_REPO_DIR"
else
  REPO_DIR=$(cd "$(dirname "$0")/../.." && pwd)
fi

# Validar que a raiz (override ou derivada) existe e e um diretorio
if [ ! -d "$REPO_DIR" ]; then
  echo "erro: raiz do repositorio invalida: $REPO_DIR (defina RANKING_MSC_REPO_DIR se o script nao estiver em <repo>/scripts/deploy/)" >&2
  exit 1
fi

# Validar que docker-compose.prod.yml existe
if [ ! -f "$REPO_DIR/docker-compose.prod.yml" ]; then
  echo "erro: docker-compose.prod.yml nao encontrado em $REPO_DIR (defina RANKING_MSC_REPO_DIR se o script nao estiver em <repo>/scripts/deploy/)" >&2
  exit 1
fi

if [ -z "${RENEWED_LINEAGE:-}" ]; then
  echo "erro: RENEWED_LINEAGE ausente (o certbot a define no deploy-hook)" >&2
  exit 1
fi

CERT_DIR="${REPO_DIR}/docker/nginx/certs"
mkdir -p "$CERT_DIR"

# Escrita atomica: escrever em temporario e depois mv.
# Assim um leitor concorrente nunca ve PEM parcial.
FULLCHAIN_TEMP="${CERT_DIR}/.fullchain.pem.tmp"
PRIVKEY_TEMP="${CERT_DIR}/.privkey.pem.tmp"

cp -L "${RENEWED_LINEAGE}/fullchain.pem" "$FULLCHAIN_TEMP"
cp -L "${RENEWED_LINEAGE}/privkey.pem" "$PRIVKEY_TEMP"

# Garantir permissoes explicitamente (umask nao garante chmod 644 em cp).
chmod 644 "$FULLCHAIN_TEMP"
chmod 600 "$PRIVKEY_TEMP"

# Mover atomicamente por cima do anterior.
mv "$FULLCHAIN_TEMP" "${CERT_DIR}/fullchain.pem"
mv "$PRIVKEY_TEMP" "${CERT_DIR}/privkey.pem"

# Garantir que fullchain.pem termina com 0644 mesmo apos mv.
chmod 644 "${CERT_DIR}/fullchain.pem"

# Recarregar o nginx se o stack estiver rodando.
# Distinguir "stack parado" (tolerar) de "stack rodando mas reload falhou" (erro).
cd "$REPO_DIR"

# Duas variaveis para que um executavel cujo caminho contenha espaco funcione
# (sempre aspeado) e o default "docker compose" continue como binario + subcomando.
# Nada aqui passa por eval.
DOCKER_COMPOSE_BIN="${DOCKER_COMPOSE_BIN:-docker}"
DOCKER_COMPOSE_SUBCMD="${DOCKER_COMPOSE_SUBCMD-compose}"

compose_cmd() {
  if [ -n "$DOCKER_COMPOSE_SUBCMD" ]; then
    "$DOCKER_COMPOSE_BIN" "$DOCKER_COMPOSE_SUBCMD" "$@"
  else
    "$DOCKER_COMPOSE_BIN" "$@"
  fi
}

# Checagem explícita de estado: nginx está rodando?
# "docker compose ps" imprime STATUS no formato humano do Docker
# ("Up 5 hours (healthy)"), nunca a palavra "running" -- um grep nela nunca
# casa, e o hook cairia sempre no ramo "stack parado" mesmo com o nginx no ar
# (bug corrigido aqui: cert novo gravado, nginx nunca recarrega, certbot
# reporta sucesso). "ps -q" devolve o ID do container quando presente
# (running/restarting/paused, por padrao) e vazio quando parado/inexistente --
# estavel entre versoes do compose, ao contrario do texto da tabela.
# Saida e status sao capturados SEPARADAMENTE. Um "ps -q" que falha (daemon
# reiniciando, plugin do compose ausente, usuario do hook sem permissao no
# socket) tambem devolve stdout vazio. Ler esse vazio como "parado" faria o hook
# pular o reload de um nginx que esta de pe -- que seguiria servindo o
# certificado antigo com a renovacao reportada como aplicada. Vazio so significa
# "parado" quando a consulta em si teve sucesso; caso contrario e "nao sei", e
# "nao sei" nao pode virar sucesso silencioso.
if nginx_id=$(compose_cmd -f docker-compose.prod.yml ps -q nginx 2>/dev/null); then
  consulta_estado_ok=1
else
  consulta_estado_ok=0
fi

if [ "$consulta_estado_ok" -eq 0 ]; then
  echo "erro: nao foi possivel consultar o estado do nginx (docker indisponivel?);" \
       "certificado copiado, mas o reload NAO foi confirmado" >&2
  exit 1
fi

if [ -n "$nginx_id" ]; then
  # Stack está rodando. Tentar reload. Se falhar, é erro real.
  if ! compose_cmd -f docker-compose.prod.yml exec -T nginx nginx -s reload 2>/dev/null; then
    echo "erro: nginx reload falhou mas stack esta rodando" >&2
    exit 1
  fi
else
  # Consulta teve sucesso e nao ha container: stack realmente parado. Toleramos.
  # Certificado já foi copiado, será lido no próximo boot.
  echo "aviso: nginx nao esta rodando; certificado copiado, sera lido no proximo boot"
fi
