# Runs untrusted Python submissions. The worker starts it with no network, no capabilities,
# a read-only root, and a tmpfs at /work (see backend/src/dailycommit/sandbox/backend.py).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=0

WORKDIR /work
USER 65534:65534
