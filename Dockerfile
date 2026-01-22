# Dockerfile para ejecutar el bot de Bixpe en Docker
# Usa imagen completa para tener todas las dependencias

FROM python:3.11

LABEL maintainer="Antonio Castillo"
LABEL description="Bot automatizado de Bixpe con Playwright y notificaciones por Telegram"

# Variables de entorno del sistema
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Instalar dependencias del sistema para Playwright/Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    curl \
    git \
    # Dependencias para Chromium
    fonts-liberation \
    libappindicator1 \
    libappindicator3-1 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libgdk-pixbuf-2.0-0 \
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
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar archivos de requisitos
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Instalar Playwright Chromium
RUN playwright install chromium

# Copiar el código de la aplicación
COPY main.py .
COPY .env.example .

# Crear directorio para logs
RUN mkdir -p /app/logs

# Comando por defecto
CMD ["python", "main.py"]

