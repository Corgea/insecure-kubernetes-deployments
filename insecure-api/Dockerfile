# syntax=docker/dockerfile:1.7
#
# Build from the repository root:
#   docker build -f insecure-api/Dockerfile -t insecure-api .

ARG PYTHON_IMAGE=python:3.11.17-slim-bookworm@sha256:0a310eeecf4e1f5a0743f9a6520c90c88d089c903ca5fd283f501e3a805f5f89

# --- build: virtualenv with the pinned requirements, plus the seeded database ---
FROM ${PYTHON_IMAGE} AS build

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /src

# Requirements first, so editing the application does not reinstall them.
COPY insecure-api/requirements.txt ./
RUN pip install -r requirements.txt

COPY insecure-api/main.py insecure-api/models.py insecure-api/database.py ./

# Importing the app here fails the build on a missing dependency, and seeding
# videogames.db now means the runtime image never writes to its working directory.
RUN python -c "import main; main.init_db()"

# --- runtime ---
FROM ${PYTHON_IMAGE}

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:${PATH}"

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app

COPY --from=build /opt/venv /opt/venv
COPY --from=build /src/videogames.db ./
COPY --from=build /src/main.py .

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/games', timeout=3)"]

# listen on all interfaces
CMD ["uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"]
