FROM docker.io/library/python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=config.settings

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install -r requirements.txt

RUN groupadd --system app && useradd --system --gid app --home-dir /app app
COPY --chown=app:app . .
RUN mkdir -p /app/media /app/private_media /app/staticfiles \
    && chown -R app:app /app/media /app/private_media /app/staticfiles

USER app
EXPOSE 8000
STOPSIGNAL SIGINT

ENTRYPOINT ["sh", "/app/docker/entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000", "--noreload"]
