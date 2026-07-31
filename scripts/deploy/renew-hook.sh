#!/bin/sh
# Deploy-hook do certbot: publica o certificado renovado no diretorio lido
# pelo nginx e recarrega o servidor sem derrubar conexoes.
#
# O certbot mantem /etc/letsencrypt/live/<dominio>/*.pem como symlinks para
# ../../archive/. Copiamos com -L (dereferencia) porque um bind mount parcial
# de live/ levaria symlinks quebrados para dentro do container.
#
# Variaveis de ambiente:
#   RANKING_MSC_REPO_DIR  raiz do repositorio (obrigatoria)
#   RENEWED_LINEAGE       definida pelo certbot: /etc/letsencrypt/live/<dominio>
#   DOCKER_COMPOSE_CMD    opcional; default "docker compose"
set -eu

if [ -z "${RANKING_MSC_REPO_DIR:-}" ]; then
  echo "erro: defina RANKING_MSC_REPO_DIR com a raiz do repositorio" >&2
  exit 1
fi

if [ -z "${RENEWED_LINEAGE:-}" ]; then
  echo "erro: RENEWED_LINEAGE ausente (o certbot a define no deploy-hook)" >&2
  exit 1
fi

CERT_DIR="${RANKING_MSC_REPO_DIR}/docker/nginx/certs"
mkdir -p "$CERT_DIR"

cp -L "${RENEWED_LINEAGE}/fullchain.pem" "${CERT_DIR}/fullchain.pem"
cp -L "${RENEWED_LINEAGE}/privkey.pem" "${CERT_DIR}/privkey.pem"
chmod 644 "${CERT_DIR}/fullchain.pem"
chmod 600 "${CERT_DIR}/privkey.pem"

# Stack fora do ar nao e erro: o certificado ja esta no lugar e sera lido no
# proximo boot. Falhar aqui abortaria a renovacao por um motivo irrelevante.
cd "$RANKING_MSC_REPO_DIR"
if ! ${DOCKER_COMPOSE_CMD:-docker compose} -f docker-compose.prod.yml \
     exec -T nginx nginx -s reload 2>/dev/null; then
  echo "aviso: nginx nao recarregado (stack fora do ar?); certificado copiado"
fi
