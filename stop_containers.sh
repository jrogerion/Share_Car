#!/usr/bin/env bash
# Para os containers do ShareCar usando Docker Compose ou Podman Compose.
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
Uso: ./stop_containers.sh [opções]

Opções:
  -d, --down        Remove os containers e a rede, preservando os volumes.
  -v, --volumes     Remove também os volumes. Implica --down e APAGA os dados.
  -y, --yes         Confirma a remoção dos volumes sem perguntar.
  -h, --help        Mostra esta ajuda.

Variáveis:
  CONTAINER_ENGINE=docker|podman
                    Força o runtime. Sem essa variável, o script tenta
                    Docker Compose, podman-compose e podman compose, nessa ordem.

Sem opções, o script apenas para os containers e preserva containers e volumes.
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

down=0
volumes=0
assume_yes=0

while (($# > 0)); do
  case "$1" in
    -d|--down)
      down=1
      ;;
    -v|--volumes)
      volumes=1
      ;;
    -y|--yes)
      assume_yes=1
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

if ((volumes)); then
  down=1
fi

[[ -f .env ]] ||
  die "Arquivo .env não encontrado. Restaure-o para que o Compose leia as variáveis necessárias."

detect_compose

if ((down)); then
  args=(down --remove-orphans)

  if ((volumes)); then
    printf 'ATENÇÃO: esta operação removerá os volumes e APAGARÁ os dados do banco, fotos e documentos.\n' >&2

    if ((!assume_yes)); then
      answer=""
      printf "Digite 'remover' para confirmar: "
      read -r answer || true
      [[ "$answer" == "remover" ]] || die "Operação cancelada."
    fi

    args+=(-v)
    "${COMPOSE[@]}" "${args[@]}"
    printf '\nContainers, rede e volumes removidos.\n'
  else
    "${COMPOSE[@]}" "${args[@]}"
    printf '\nContainers e rede removidos. Volumes preservados.\n'
  fi
else
  "${COMPOSE[@]}" stop
  printf '\nContainers parados. Containers e volumes preservados.\n'
fi

"${COMPOSE[@]}" ps
