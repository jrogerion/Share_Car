#!/usr/bin/env bash
# Sobe os containers do ShareCar usando Docker Compose ou Podman Compose.
set -euo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

COMPOSE=()

die() {
  printf 'Erro: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Uso: ./start_containers.sh [opções]

Opções:
  -b, --build       Reconstrói as imagens antes de subir (padrão).
      --no-build    Sobe sem reconstruir as imagens.
      --reuse       Reutiliza containers existentes. Pode manter código antigo.
      --no-recreate Mesmo efeito de --reuse.
  -f, --follow      Acompanha os logs do serviço web depois de subir.
  -h, --help        Mostra esta ajuda.

Variáveis:
  CONTAINER_ENGINE=docker|podman
                    Força o runtime. Sem essa variável, o script tenta
                    Docker Compose, podman-compose e podman compose, nessa ordem.

O script usa o arquivo .env da raiz do projeto e não remove volumes.
EOF
}

detect_compose() {
  local forced="${CONTAINER_ENGINE:-}"

  if [[ -n "$forced" ]]; then
    case "$forced" in
      docker)
        command -v docker >/dev/null 2>&1 || die "docker não encontrado."
        docker compose version >/dev/null 2>&1 ||
          die "plugin Docker Compose não encontrado."
        COMPOSE=(docker compose)
        ;;
      podman)
        if command -v podman-compose >/dev/null 2>&1; then
          COMPOSE=(podman-compose)
        elif command -v podman >/dev/null 2>&1 &&
             podman compose version >/dev/null 2>&1; then
          COMPOSE=(podman compose)
        else
          die "Podman Compose não encontrado."
        fi
        ;;
      *)
        die "CONTAINER_ENGINE deve ser 'docker' ou 'podman'."
        ;;
    esac
  elif command -v docker >/dev/null 2>&1 &&
       docker compose version >/dev/null 2>&1; then
    COMPOSE=(docker compose)
  elif command -v podman-compose >/dev/null 2>&1; then
    COMPOSE=(podman-compose)
  elif command -v podman >/dev/null 2>&1 &&
       podman compose version >/dev/null 2>&1; then
    COMPOSE=(podman compose)
  else
    die "Docker Compose ou Podman Compose não encontrado."
  fi

  printf 'Runtime: %s\n' "${COMPOSE[*]}"
}

env_value() {
  local key="$1"
  local fallback="$2"
  local value=""

  if [[ -f .env ]]; then
    value="$(sed -n "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*//p" .env |
      tail -n 1 | tr -d '\r')"
    value="$(printf '%s' "$value" | sed -e 's/^["'\'']//' -e 's/["'\'']$//')"
  fi

  printf '%s' "${value:-$fallback}"
}

build=1
follow=0
recreate=1

while (($# > 0)); do
  case "$1" in
    -b|--build)
      build=1
      ;;
    --no-build)
      build=0
      ;;
    --reuse|--no-recreate)
      recreate=0
      ;;
    -f|--follow)
      follow=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    *)
      die "Opção desconhecida: $1 (use --help)."
      ;;
  esac
  shift
done

[[ -f .env ]] ||
  die "Arquivo .env não encontrado. Crie com 'cp .env.example .env' e preencha DJANGO_SECRET_KEY e POSTGRES_PASSWORD."

detect_compose

args=(up -d)
if ((build)); then
  args+=(--build)
fi
if ((recreate)); then
  args+=(--force-recreate)
fi

if ((!recreate)); then
  printf 'Aviso: --reuse mantém os containers atuais e pode deixar código antigo em execução.\n' >&2
fi

if ! "${COMPOSE[@]}" "${args[@]}"; then
  die "Não foi possível iniciar os containers. Consulte os logs com: ${COMPOSE[*]} logs db web"
fi

host="$(env_value DJANGO_BIND_ADDRESS 127.0.0.1)"
port="$(env_value DJANGO_HOST_PORT 8000)"

# Um bind em todas as interfaces continua acessível pelo loopback nesta máquina.
if [[ "$host" == "0.0.0.0" || "$host" == "::" ]]; then
  host="127.0.0.1"
fi

printf '\nContainers em execução.\n\n'
"${COMPOSE[@]}" ps
printf '\nAcesse a home page do site:\n  http://%s:%s/\n' "$host" "$port"
printf '\nPainel administrativo:\n  http://%s:%s/admin/\n' "$host" "$port"
printf '\nCriar administrador: %s exec web python manage.py createsuperuser\n' "${COMPOSE[*]}"

if ((follow)); then
  printf '\nAcompanhando os logs do serviço web. Ctrl+C encerra apenas os logs.\n'
  exec "${COMPOSE[@]}" logs -f web
fi
