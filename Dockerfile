# The stage B upload API (ADR 0005) as a container image, run by Cloudflare Containers (deploy/api).
# Build: docker build -t aai-api .   Run: docker run -p 8080:8080 -e AIP_API_KEYS='{"<sha256>":"tenant_x"}' aai-api
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 AIP_HOME=/app AIP_DATA_DIR=/data

COPY pyproject.toml README.md LICENSE ./
COPY requirements/constraints.txt requirements/constraints.txt
COPY src src
COPY schemas schemas
COPY registry registry
RUN pip install --no-cache-dir -c requirements/constraints.txt ".[api,modeling]" \
    && useradd --create-home --uid 10001 aip \
    && mkdir /data && chown aip /data

USER aip
EXPOSE 8080
# Uploads live on the container's own disk and are deleted after AIP_RETENTION_HOURS (default 24) or when the
# container stops, whichever comes first.
CMD ["uvicorn", "--factory", "aip.api.app:app_from_env", "--host", "0.0.0.0", "--port", "8080"]
