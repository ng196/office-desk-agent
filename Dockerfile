# NOT USED: Fly.io hosting was dropped ($0 budget). Kept for reference only; the engine runs locally (see CORE.md).
# Demo web app (Fly.io). Keys come from `fly secrets`, never from this image (.dockerignore drops .env).
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    DESK_MODE=demo DESK_DATA_DIR=/data HF_HOME=/data/cache DESK_CACHE=/data/cache DESK_SEED_DB=/app/seed/index.db
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY desk/ desk/
COPY mockup/ mockup/
# public-samples index, copied to /data/index.db on first boot
COPY data/index.db seed/index.db
EXPOSE 8080
CMD ["uvicorn", "desk.web:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]