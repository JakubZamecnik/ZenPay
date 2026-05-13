FROM python:3.11-slim

WORKDIR /app

# Instalace systémových závislostí pro kompilaci některých balíčků
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Kopírování závislostí a jejich instalace
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Kopírování zdrojového kódu aplikace
COPY app/ ./app/

# Port, na kterém poběží FastAPI
EXPOSE 8000
