# Dockerfile para ejecutar el bot de Bixpe en Docker
# Imagen base Python con Playwright preinstalado

FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

LABEL maintainer="Antonio Castillo"
LABEL description="Bot automatizado de Bixpe con Playwright y notificaciones por Telegram"

# Variables de entorno del sistema
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Crear directorio de trabajo
WORKDIR /app

# Copiar archivos de requisitos
COPY requirements.txt .

# Actualizar pip e instalar dependencias y tzdata
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y tzdata && \
    pip install --upgrade pip && \
    pip install --no-cache-dir playwright && \
    pip install --no-cache-dir -r requirements.txt && \
    playwright install chromium && \
    rm -rf /var/lib/apt/lists/*

# Configurar zona horaria
ENV TZ=Europe/Madrid

# Copiar el código de la aplicación
COPY main.py .
COPY .env.example .

# Crear directorio para logs
RUN mkdir -p /app/logs

# Comando por defecto
CMD ["python", "main.py"]

