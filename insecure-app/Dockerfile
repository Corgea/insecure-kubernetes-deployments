# syntax=docker/dockerfile:1.7
#
# Build from the repository root:
#   docker build -f insecure-app/Dockerfile -t insecure-app .

ARG PYTHON_IMAGE=python:3.11.17-slim-bookworm@sha256:0a310eeecf4e1f5a0743f9a6520c90c88d089c903ca5fd283f501e3a805f5f89

# --- build: virtualenv with the pinned requirements ---
FROM ${PYTHON_IMAGE} AS build

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

COPY insecure-app/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

# --- runtime ---
FROM ${PYTHON_IMAGE}

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:${PATH}"

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app

COPY --from=build /opt/venv /opt/venv

# The index view opens tutorial.db relative to the working directory on every
# request; ship the seeded copy rather than let it create an empty one.
COPY insecure-app/tutorial.db ./
COPY insecure-app/app.py ./

# The Werkzeug debugger executes arbitrary code from the browser, so the image
# never runs with debug enabled.
RUN sed -i '' 's/debug=True/debug=False/' app.py

# Target directory for the upload form.
RUN mkdir -p /uploads

USER app

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/', timeout=3)"]

CMD ["python", "app.py"]
