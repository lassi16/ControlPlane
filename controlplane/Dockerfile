FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Create __init__ files
RUN find . -type d -exec touch {}/__init__.py \;

EXPOSE 8000

ENV PYTHONPATH=/app

CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
