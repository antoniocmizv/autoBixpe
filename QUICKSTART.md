# Guía de inicio rápido para desplegar en Portainer

## 📋 Pasos previos

1. **Tener Git instalado**
2. **Acceso a un servidor con Docker + Portainer**
3. **Token de Telegram y Chat ID**
4. **Credenciales de Bixpe**

## 🚀 Opción 1: Desplegar desde GitHub (Recomendado)

### En el servidor:

```bash
# Clonar repositorio
git clone https://github.com/tu-usuario/autoBixpe.git
cd autoBixpe

# Crear archivo .env con tus credenciales
cat > .env << EOF
BIXPE_USERNAME=tu_usuario@email.com
BIXPE_PASSWORD=tu_contraseña
TELEGRAM_TOKEN=123456789:ABCdefGHIjklmnoPQRstuvWXYZ
TELEGRAM_CHAT_ID=987654321
HEADLESS=true
EOF

# Iniciar con Docker Compose
docker-compose up -d
```

## 🐳 Opción 2: Portainer Stack UI

### 1. Acceder a Portainer
- URL: `http://tu-servidor:9000`
- Inicia sesión

### 2. Crear Stack
- Menú → `Stacks`
- `+ Add Stack`
- Nombre: `bixpe-automation`

### 3. Pegar docker-compose.yml
En el editor:
```yaml
version: '3.8'

services:
  bixpe-bot:
    build: https://github.com/tu-usuario/autoBixpe.git
    container_name: bixpe-automation
    restart: unless-stopped
    environment:
      - BIXPE_USERNAME=${BIXPE_USERNAME}
      - BIXPE_PASSWORD=${BIXPE_PASSWORD}
      - TELEGRAM_TOKEN=${TELEGRAM_TOKEN}
      - TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}
      - HEADLESS=true
    volumes:
      - ./logs:/app/logs
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### 4. Agregar Variables de Entorno
En **Environment variables** agrega:

| Variable | Valor |
|----------|-------|
| BIXPE_USERNAME | tu_usuario@email.com |
| BIXPE_PASSWORD | tu_contraseña |
| TELEGRAM_TOKEN | token_aqui |
| TELEGRAM_CHAT_ID | chat_id_aqui |
| HEADLESS | true |

### 5. Deploy
- Click `Deploy the stack`
- Espera a que termine
- ✅ ¡Listo!

## 📊 Ver logs en Portainer

- `Containers` → `bixpe-automation` → `Logs`
- O terminal: `docker logs -f bixpe-automation`

## 🔄 Actualizar

```bash
# En el servidor:
cd autoBixpe
git pull origin main
docker-compose down
docker-compose up -d --build
```

## 🐛 Si algo falla

```bash
# Ver logs
docker logs bixpe-automation

# Reiniciar contenedor
docker-compose restart

# Reconstruir imagen
docker-compose build --no-cache
docker-compose up -d
```

## 🔐 Secure: Usar Docker Secrets (Avanzado)

Si usas Docker Swarm en Portainer:

```bash
echo "tu_usuario@email.com" | docker secret create bixpe_username -
echo "tu_contraseña" | docker secret create bixpe_password -
echo "token_aqui" | docker secret create telegram_token -
echo "chat_id" | docker secret create telegram_chat_id -
```

Luego en docker-compose:
```yaml
services:
  bixpe-bot:
    environment:
      - BIXPE_USERNAME_FILE=/run/secrets/bixpe_username
```

---

**¿Preguntas?** Revisa el README.md principal
