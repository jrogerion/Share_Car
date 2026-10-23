#!/bin/sh
set -eu

# Verifica uma consulta autenticada, não apenas uma porta TCP aberta.
python - <<'PY'
import os
import time

import django
from django.db import OperationalError, connection

django.setup()
limite = time.monotonic() + int(os.environ.get("DB_WAIT_TIMEOUT", "60"))
print("Aguardando PostgreSQL...", flush=True)
while True:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        break
    except OperationalError:
        connection.close()
        if time.monotonic() >= limite:
            raise SystemExit("PostgreSQL indisponível: confira host, porta e credenciais.")
        time.sleep(2)
connection.close()
print("PostgreSQL pronto.", flush=True)
PY

python manage.py migrate --noinput
exec "$@"
