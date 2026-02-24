FROM python:3.13-slim AS builder

WORKDIR /build

RUN pip install --no-cache-dir build

COPY pyproject.toml README.md ./
COPY src/ src/

RUN python -m build --wheel --outdir /build/wheels

FROM python:3.13-slim

WORKDIR /app

COPY --from=builder /build/wheels/*.whl /tmp/wheels/
RUN pip install --no-cache-dir /tmp/wheels/*.whl && rm -rf /tmp/wheels

EXPOSE 18800 18801

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:18800/api/health')" || exit 1

ENTRYPOINT ["labclaw", "serve", "--host", "0.0.0.0"]
