# Dockerfile para ejecutar el bot de Bixpe en Docker
# Optimizado para producción

FROM python:3.11-slim

LABEL maintainer="Antonio Castillo <antonio.m.castillo.morales@gmail.com>"
LABEL description="Bot automatizado de Bixpe con Playwright y notificaciones por Telegram"

# Variables de entorno del sistema
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Instalar todas las dependencias necesarias para Playwright en un solo paso
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Herramientas básicas
    wget \
    curl \
    git \
    # Dependencias de Playwright/Chromium
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libgconf-2-4 \
    libgdk-pixbuf2.0-0 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    xdg-utils \
    fonts-liberation \
    libappindicator3-1 \
    # Otros
    ca-certificates \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar archivos de requisitos
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Instalar solo Chromium de Playwright (más ligero)
RUN playwright install chromium

# Copiar el código de la aplicación
COPY main.py .
COPY .env.example .

# Crear directorio para logs
RUN mkdir -p /app/logs

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Comando por defecto
CMD ["python", "main.py"]

