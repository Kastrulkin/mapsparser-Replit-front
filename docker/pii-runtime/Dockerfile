FROM localos-pii-pilot:vps-20261102
USER root
RUN python -m pip install --no-cache-dir gunicorn==26.2.0 && python -m pip check
COPY src/services/pii_protection /opt/pii/src/services/pii_protection
COPY docker/pii-runtime/gunicorn.conf.py /opt/pii/gunicorn.conf.py
COPY docker/pii-runtime/provision.py docker/pii-runtime/healthcheck.py /opt/pii/
ENV PYTHONPATH=/opt/pii/src PYTHONDONTWRITEBYTECODE=1 \
    PII_PROTECTION_ENABLED=false OTEL_SDK_DISABLED=true \
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
USER 10001
WORKDIR /opt/pii
CMD ["gunicorn", "--config", "/opt/pii/gunicorn.conf.py", "services.pii_protection.runtime_server:create_app()"]
