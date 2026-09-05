FROM python:3.12-slim

RUN useradd --create-home --uid 10001 gateway && useradd --create-home --uid 10002 sandbox
WORKDIR /runner
COPY server.py /runner/server.py
EXPOSE 8091
CMD ["python", "-I", "/runner/server.py"]
