# ---- Base image
FROM python:3.12-slim AS base

# Sistem paketleri (sqlite3 & build essentials)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git sqlite3 ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Çalışma dizini
WORKDIR /app

# Python env
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_NO_CACHE_DIR=1

# Bağımlılıkları cache-dostu kopyala
COPY requirements.txt ./
RUN python -m pip install --upgrade pip && \
    pip install -r requirements.txt

# Uygulama kodu
COPY src ./src
COPY scripts ./scripts
COPY data ./data
COPY .env .env
COPY pytest.ini pytest.ini
COPY README.md README.md

# Streamlit yapılandırması
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Varsayılan komut
CMD ["streamlit", "run", "src/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
