FROM python:3.12-slim@sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_PYTHON_VERSION_WARNING=1 \
    APP_ENV=production \
    AUTO_CREATE_DB_SCHEMA=false \
    REQUIRE_DB_MIGRATIONS=true \
    ENABLE_JOB_BROWSER_FALLBACK=false \
    RESUMEPILOT_DATA_DIR=/data

WORKDIR /app

ARG TECTONIC_VERSION=0.16.9
ARG TECTONIC_SHA256=f3c825128095dc3399ea11c08c18035b33050a216930c295c79e8eb11bd21de4
ARG TARGETARCH

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

RUN if [ "${TARGETARCH}" = "amd64" ]; then \
      archive="/tmp/tectonic-${TECTONIC_VERSION}.tar.gz"; \
      curl --fail --location --retry 3 --silent --show-error \
        "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40${TECTONIC_VERSION}/tectonic-${TECTONIC_VERSION}-x86_64-unknown-linux-gnu.tar.gz" \
        --output "${archive}"; \
      echo "${TECTONIC_SHA256}  ${archive}" | sha256sum --check; \
      tar --extract --gzip --file "${archive}" --directory /tmp tectonic; \
      install --mode 0755 /tmp/tectonic /usr/local/bin/tectonic; \
      rm -f "${archive}" /tmp/tectonic; \
      tectonic --version; \
    else \
      echo "Tectonic binary installation skipped for TARGETARCH=${TARGETARCH}"; \
    fi

COPY pyproject.toml README.md ./
COPY requirements ./requirements
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app
COPY scripts ./scripts

RUN python -m pip install --require-hashes -r requirements/py312-build.lock.txt \
    && python -m pip install --require-hashes -r requirements/py312-production.lock.txt \
    && python -m pip install --no-deps --no-build-isolation -e . \
    && python -m pip check

RUN useradd --create-home --shell /usr/sbin/nologin resumepilot \
    && mkdir -p /data \
    && chown -R resumepilot:resumepilot /data /app

USER resumepilot

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
