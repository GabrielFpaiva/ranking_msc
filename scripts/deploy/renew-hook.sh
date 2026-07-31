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

# Fechar janela de permissao: umask evita que privkey fique legivel ao grupo/outros
# entre o cp e o chmod.
umask 077

if [ -z "${RANKING_MSC_REPO_DIR:-}" ]; then
  echo "erro: defina RANKING_MSC_REPO_DIR com a raiz do repositorio" >&2
  exit 1
fi

# Validar que RANKING_MSC_REPO_DIR existe e e um diretorio
if [ ! -d "$RANKING_MSC_REPO_DIR" ]; then
  echo "erro: RANKING_MSC_REPO_DIR nao e um diretorio: $RANKING_MSC_REPO_DIR" >&2
  exit 1
fi

# Validar que docker-compose.prod.yml existe
if [ ! -f "$RANKING_MSC_REPO_DIR/docker-compose.prod.yml" ]; then
  echo "erro: docker-compose.prod.yml nao encontrado em $RANKING_MSC_REPO_DIR" >&2
  exit 1
fi

if [ -z "${RENEWED_LINEAGE:-}" ]; then
  echo "erro: RENEWED_LINEAGE ausente (o certbot a define no deploy-hook)" >&2
  exit 1
fi

CERT_DIR="${RANKING_MSC_REPO_DIR}/docker/nginx/certs"
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
cd "$RANKING_MSC_REPO_DIR"

# Checagem explícita de estado: nginx está rodando?
# Usamos 'docker compose ps' para ver se o serviço está running.
# Tratamos a variável DOCKER_COMPOSE_CMD como array via set --.
if [ -z "${DOCKER_COMPOSE_CMD:-}" ]; then
  set -- docker compose
else
  # Resolver a variável como um comando (pode ter espaços, ex: "/path/to/docker compose")
  # Usamos eval de forma controlada aqui apenas para split DOCKER_COMPOSE_CMD
  eval "set -- $DOCKER_COMPOSE_CMD"
fi

# Tentar verificar estado do nginx
if "$@" -f docker-compose.prod.yml ps nginx 2>/dev/null | grep -q running; then
  # Stack está rodando. Tentar reload. Se falhar, é erro real.
  if ! "$@" -f docker-compose.prod.yml exec -T nginx nginx -s reload 2>/dev/null; then
    echo "erro: nginx reload falhou mas stack esta rodando" >&2
    exit 1
  fi
else
  # Stack não está rodando (ou nginx não existe). Toleramos.
  # Certificado já foi copiado, será lido no próximo boot.
  echo "aviso: nginx nao esta rodando; certificado copiado, sera lido no proximo boot"
fi
