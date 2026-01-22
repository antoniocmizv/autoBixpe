# Dockerfile para ejecutar el bot de Bixpe en Docker
# Usa imagen oficial de Playwright que ya tiene todo pre-instalado

FROM mcr.microsoft.com/playwright/python:v1.48.0-focal

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

# Instalar dependencias de Python (sin Playwright porque ya está en la imagen)
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la aplicación
COPY main.py .
COPY .env.example .

# Crear directorio para logs
RUN mkdir -p /app/logs

# Comando por defecto
CMD ["python", "main.py"]

