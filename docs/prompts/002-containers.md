# Etapa 2 — Containers e tutorial

Solicitação: configurar Django e PostgreSQL em dois containers, com Dockerfile,
Compose compatível com Docker e Podman, volume persistente, porta do banco
publicada para psql/pgAdmin, variáveis no .env e espera pela prontidão do banco.
Documentar instalação, execução, migrações e remoção sem perda dos dados.

Decisões: Python 3.14, PostgreSQL 18, portas locais 8000/5432 configuráveis,
espera autenticada no entrypoint e migrações aplicadas antes do servidor de
desenvolvimento. Código incorporado à imagem para evitar diferenças de bind
mount/permissões/SELinux entre ambientes; modelos continuam nos sete apps.
