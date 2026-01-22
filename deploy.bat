@echo off
REM Script de despliegue para Windows

echo.
echo 🚀 Despliegue de autoBixpe (Windows)
echo ================================
echo.

REM Verificar Docker
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker no está instalado
    exit /b 1
)

echo ✅ Docker encontrado
echo.

REM Crear directorio si no existe
if not exist "autoBixpe" (
    echo 📦 Clonando repositorio...
    git clone https://github.com/tu-usuario/autoBixpe.git
)

cd autoBixpe

REM Crear .env si no existe
if not exist ".env" (
    echo ⚠️  Archivo .env no encontrado
    echo Creando .env...
    echo.
    
    set /p BIXPE_USERNAME="Usuario de Bixpe: "
    set /p BIXPE_PASSWORD="Contraseña de Bixpe: "
    set /p TELEGRAM_TOKEN="Token de Telegram: "
    set /p TELEGRAM_CHAT_ID="Chat ID de Telegram: "
    
    (
        echo BIXPE_USERNAME=%BIXPE_USERNAME%
        echo BIXPE_PASSWORD=%BIXPE_PASSWORD%
        echo TELEGRAM_TOKEN=%TELEGRAM_TOKEN%
        echo TELEGRAM_CHAT_ID=%TELEGRAM_CHAT_ID%
        echo HEADLESS=true
    ) > .env
    
    echo ✅ Archivo .env creado
    echo.
) else (
    echo ✅ Archivo .env encontrado
    echo.
)

REM Desplegar
echo 🐳 Iniciando contenedor...
docker-compose up -d

echo.
echo ✅ Despliegue completado
echo.
echo 📊 Ver logs:
echo   docker-compose logs -f
echo.
echo 🛑 Detener:
echo   docker-compose down
echo.
echo 🔄 Actualizar:
echo   git pull
echo   docker-compose build --no-cache
echo   docker-compose up -d
echo.
pause
