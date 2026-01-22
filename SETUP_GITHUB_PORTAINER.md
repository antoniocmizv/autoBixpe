# 📋 Checklist: Subir a GitHub y Desplegar en Portainer

## Paso 1: Preparar el repositorio local

```bash
cd autoBixpe
git init
git add .
git commit -m "Initial commit: Bot automatizado de Bixpe"
```

## Paso 2: Crear repositorio en GitHub

1. Ve a https://github.com/new
2. Nombre: `autoBixpe`
3. Descripción: "Bot automatizado de Bixpe con Playwright y Telegram"
4. Elige "Public" o "Private"
5. NO inicialices con README (ya lo tenemos)
6. Click "Create repository"

## Paso 3: Conectar con GitHub

```bash
git remote add origin https://github.com/tu-usuario/autoBixpe.git
git branch -M main
git push -u origin main
```

## Paso 4: Configurar Docker Hub (Opcional pero recomendado)

1. Ve a https://hub.docker.com/signup
2. Crea una cuenta
3. Ve a `Account Settings` → `Security`
4. Crea un "New Access Token"
5. Copia el token

## Paso 5: Configurar GitHub Secrets

1. Ve a tu repositorio en GitHub
2. `Settings` → `Secrets and variables` → `Actions`
3. Haz click en `New repository secret`

**Agrega dos secretos:**

| Name | Value |
|------|-------|
| `DOCKER_USERNAME` | Tu usuario de Docker Hub |
| `DOCKER_PASSWORD` | El token de acceso que copiaste |

## Paso 6: Verificar GitHub Actions

1. Ve a la pestaña `Actions` en tu repositorio
2. Deberías ver el workflow `docker-build.yml`
3. Si hiciste push a `main`, debería estar corriendo
4. Espera a que termine
5. Si es exitoso, tu imagen está en Docker Hub

## Paso 7: Desplegar en Portainer

### Opción A: Usando Docker Compose en servidor

```bash
# En tu servidor
git clone https://github.com/tu-usuario/autoBixpe.git
cd autoBixpe

# Crear .env
nano .env
# Agrega tus credenciales

# Iniciar
docker-compose up -d
```

### Opción B: Portainer UI Stack

1. Accede a Portainer: `http://servidor:9000`
2. `Stacks` → `+ Add Stack`
3. Nombre: `bixpe-automation`
4. Pega este docker-compose:

```yaml
version: '3.8'

services:
  bixpe-bot:
    image: tu-usuario/autobixpe:latest
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

5. En `Environment` agrega:
   - `BIXPE_USERNAME=tu_email`
   - `BIXPE_PASSWORD=tu_pass`
   - `TELEGRAM_TOKEN=token`
   - `TELEGRAM_CHAT_ID=chat_id`

6. Click `Deploy`

### Opción C: Portainer UI Container

1. `Containers` → `+ Add Container`
2. Name: `bixpe-automation`
3. Image: `tu-usuario/autobixpe:latest`
4. Agrega env vars (ver arriba)
5. `Deploy`

## Paso 8: Monitorear

```bash
# En servidor
docker logs -f bixpe-automation

# O en Portainer UI
Containers → bixpe-automation → Logs
```

## Actualizar en el futuro

Cada vez que hagas `git push` a `main`:

1. GitHub Actions construye automáticamente la imagen
2. Se sube a Docker Hub
3. En Portainer: `Containers` → `bixpe-automation` → `Recreate`

O en terminal:
```bash
cd autoBixpe
git pull
docker-compose pull
docker-compose up -d
```

---

## ⚠️ Checklist de seguridad

- ✅ `.env` NO subido a GitHub (.gitignore)
- ✅ Secretos configurados en GitHub
- ✅ Contraseña de Bixpe no en código
- ✅ Token de Telegram no en código
- ✅ README.md sin credenciales de ejemplo reales
- ✅ .gitignore tiene `__pycache__/` y archivos temp

## Troubleshooting

**Image not found**
```bash
docker pull tu-usuario/autobixpe:latest
```

**Permission denied in Portainer**
- Verifica que el usuario tenga permisos de Docker

**Container no inicia**
```bash
docker logs bixpe-automation
```

**Código desactualizado en Portainer**
```bash
docker pull tu-usuario/autobixpe:latest
docker-compose up -d
```

---

¡Listo! Tu bot está en producción 🚀
