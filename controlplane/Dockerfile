FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Ensure all packages are importable
ENV PYTHONPATH=/app

# Create data dir for SQLite
RUN mkdir -p /app/data

EXPOSE 8000

# Use $PORT if set (Railway injects it), else default 8000
CMD uvicorn gateway.main:app --host 0.0.0.0 --port ${PORT:-8000}
