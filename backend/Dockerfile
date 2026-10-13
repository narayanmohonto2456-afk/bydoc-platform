# syntax=docker/dockerfile:1
FROM python:3.12-slim-trixie AS build

ENV VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app/backend
RUN python -m venv /opt/venv
COPY requirements/base.txt requirements/production.txt requirements/
RUN pip install --no-cache-dir -r requirements/production.txt && pip check
RUN apt-get update && apt-get install --yes --no-install-recommends gettext \
    && rm -rf /var/lib/apt/lists/*
COPY . .
RUN DJANGO_SETTINGS_MODULE=config.settings.build python manage.py compilemessages -l bn -l hi \
    && DJANGO_SETTINGS_MODULE=config.settings.build python manage.py collectstatic --noinput

FROM python:3.12-slim-trixie
ENV VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    DJANGO_SETTINGS_MODULE=config.settings.production \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app/backend
# Render runtime secret files are readable by group 1000.
RUN groupadd --system app && groupadd --gid 1000 secrets \
    && useradd --system --gid app --groups secrets --home-dir /app app
COPY --from=build /opt/venv /opt/venv
COPY --from=build --chown=app:app /app/backend /app/backend
USER app
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-", "--error-logfile", "-"]
