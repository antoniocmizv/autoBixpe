#!/bin/bash
# Script de despliegue rápido en servidor con Docker

set -e

echo "🚀 Despliegue de autoBixpe"
echo "================================"

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Verificar Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker no está instalado${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker encontrado${NC}"

# Crear directorio si no existe
if [ ! -d "autoBixpe" ]; then
    echo "📦 Clonando repositorio..."
    git clone https://github.com/tu-usuario/autoBixpe.git
fi

cd autoBixpe

# Crear .env si no existe
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  Archivo .env no encontrado${NC}"
    echo "Creando .env..."
    
    read -p "Usuario de Bixpe: " BIXPE_USERNAME
    read -sp "Contraseña de Bixpe: " BIXPE_PASSWORD
    echo
    read -p "Token de Telegram: " TELEGRAM_TOKEN
    read -p "Chat ID de Telegram: " TELEGRAM_CHAT_ID
    
    cat > .env << EOF
BIXPE_USERNAME=$BIXPE_USERNAME
BIXPE_PASSWORD=$BIXPE_PASSWORD
TELEGRAM_TOKEN=$TELEGRAM_TOKEN
TELEGRAM_CHAT_ID=$TELEGRAM_CHAT_ID
HEADLESS=true
EOF
    
    echo -e "${GREEN}✅ Archivo .env creado${NC}"
else
    echo -e "${GREEN}✅ Archivo .env encontrado${NC}"
fi

# Desplegar
echo -e "${YELLOW}🐳 Iniciando contenedor...${NC}"
docker-compose up -d

echo -e "${GREEN}✅ Despliegue completado${NC}"
echo ""
echo "📊 Ver logs:"
echo "  docker-compose logs -f"
echo ""
echo "🛑 Detener:"
echo "  docker-compose down"
echo ""
echo "🔄 Actualizar:"
echo "  git pull && docker-compose build --no-cache && docker-compose up -d"
