# syntax=docker/dockerfile:1.9
# Multi-stage build — final image is ~60 MB (slim + no build deps)

# ── Build stage ──────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build deps
RUN pip install --no-cache-dir build==1.2.2

COPY pyproject.toml README.md ./
COPY src/ src/

RUN python -m build --wheel --outdir /dist

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="logpilot" \
      org.opencontainers.image.description="Fast, extensible log analysis CLI" \
      org.opencontainers.image.licenses="MIT"

# Non-root user for security
RUN useradd --create-home --shell /bin/bash logpilot
WORKDIR /home/logpilot

# Install the built wheel + optional extras
COPY --from=builder /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl "$(ls /tmp/*.whl | head -1)[redis,alerts]" \
    && rm /tmp/*.whl

USER logpilot

# Mount log files at /logs
VOLUME ["/logs"]

ENTRYPOINT ["logpilot"]
CMD ["--help"]
