FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends redis-server \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home pilot
COPY requirements.pii.txt requirements.pii-pilot.txt /opt/pilot-deps/
RUN python -m pip install --no-cache-dir -r /opt/pilot-deps/requirements.pii-pilot.txt
USER 10001
WORKDIR /opt/pilot
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/opt/pilot/src \
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false \
    PII_PROTECTION_ENABLED=false
