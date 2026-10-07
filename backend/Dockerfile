# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm AS build

ENV VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app/backend
RUN python -m venv /opt/venv
COPY requirements/base.txt requirements/base.txt
RUN pip install --no-cache-dir -r requirements/base.txt
RUN apt-get update && apt-get install --yes --no-install-recommends gettext \
    && rm -rf /var/lib/apt/lists/*
COPY . .
RUN DJANGO_SETTINGS_MODULE=config.settings.build python manage.py compilemessages -l bn -l hi \
    && DJANGO_SETTINGS_MODULE=config.settings.build python manage.py collectstatic --noinput

FROM python:3.12-slim-bookworm
ENV VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    DJANGO_SETTINGS_MODULE=config.settings.production \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app/backend
RUN groupadd --system app && useradd --system --gid app --home-dir /app app
COPY --from=build /opt/venv /opt/venv
COPY --from=build --chown=app:app /app/backend /app/backend
USER app
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-", "--error-logfile", "-"]
