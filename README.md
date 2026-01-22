# 🤖 Bot Automatizado de Bixpe con Telegram

Automatiza el login en Bixpe a horas específicas (9:00 y 18:00), inicia/detiene jornada y envía capturas de pantalla por Telegram. Diseñado para ejecutarse en Docker con Portainer.

## 📋 Características

✅ Login automático a las 9:00 (Iniciar jornada)  
✅ Stop automático a las 18:00 (Finalizar jornada)  
✅ Confirmación automática de popups  
✅ Envío de capturas por Telegram  
✅ Chrome Headless con Playwright  
✅ Containerizado en Docker  
✅ Compatible con Portainer  
✅ Detección automática de hora más cercana  

## 🔧 Requisitos

- **Local**: Python 3.11+, Docker, Docker Compose
- **Servidor**: Docker + Portainer
- **Telegram**: Bot Token y Chat ID
- **Bixpe**: Usuario y contraseña

## 📱 Configuración de Telegram

### 1. Crear Bot en Telegram

1. Abre Telegram y busca **@BotFather**
2. Envía `/newbot`
3. Sigue las instrucciones para crear tu bot
4. Copia el **Token** que te proporcione

### 2. Obtener Chat ID

1. Envía cualquier mensaje a tu bot recién creado
2. Abre en navegador: `https://api.telegram.org/bot<TOKEN>/getUpdates`
   - Reemplaza `<TOKEN>` con tu token real
3. Busca la respuesta JSON y localiza: `"chat":{"id":123456789}`
4. Ese número es tu **CHAT_ID**

## 🚀 Instalación Local

### 1. Clonar repositorio

```bash
git clone https://github.com/tu-usuario/autoBixpe.git
cd autoBixpe
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
```

Edita `.env`:

```ini
BIXPE_USERNAME=tu_usuario@email.com
BIXPE_PASSWORD=tu_contraseña
TELEGRAM_TOKEN=123456789:ABCdefGHIjklmnoPQRstuvWXYZ
TELEGRAM_CHAT_ID=987654321
HEADLESS=false
```

### 3. Ejecutar con Docker Compose

```bash
docker-compose up -d
```

Ver logs:

```bash
docker-compose logs -f
```

Detener:

```bash
docker-compose down
```

## 🐳 Despliegue en Portainer

### Opción 1: Portainer Stack (Recomendado)

1. **Acceder a Portainer**
   - URL: `http://tu-servidor:9000`
   - Inicia sesión

2. **Crear Stack**
   - Ir a: `Stacks` → `+ Add stack`
   - Nombre: `bixpe-automation`
   - **Editor**: Pega el contenido de `docker-compose.yml`

3. **Configurar variables**
   - En la sección de **Environment** agrega:
     ```
     BIXPE_USERNAME=tu_usuario@email.com
     BIXPE_PASSWORD=tu_contraseña
     TELEGRAM_TOKEN=tu_token
     TELEGRAM_CHAT_ID=tu_chat_id
     HEADLESS=true
     ```

4. **Deploy**
   - Click en `Deploy the stack`
   - Espera a que se cree la imagen y se inicie

### Opción 2: Portainer Container

1. **Ir a Containers** → **+ Add Container**

2. **Configurar:**
   - **Name**: `bixpe-automation`
   - **Image**: `tu-usuario/autobixpe:latest` (si subiste a Docker Hub)
   - O construir localmente: `bixpe-automation` (desplegable)

3. **Environment variables:**
   ```
   BIXPE_USERNAME=tu_usuario@email.com
   BIXPE_PASSWORD=tu_contraseña
   TELEGRAM_TOKEN=tu_token
   TELEGRAM_CHAT_ID=tu_chat_id
   HEADLESS=true
   ```

4. **Restart policy**: `Unless stopped`

5. **Deploy**

## 🔄 Actualizar código desde GitHub

### Con Docker Compose

```bash
git pull origin main
docker-compose build --no-cache
docker-compose up -d
```

### Con Portainer Stack

1. Ir a `Stacks` → seleccionar `bixpe-automation`
2. Click en `Edit`
3. Actualizar el código o cambiar versión de imagen
4. Click en `Update the stack`

## 📊 Monitoreo

### Ver logs en Portainer

1. `Containers` → `bixpe-automation` → `Logs`
2. O desde terminal: `docker logs -f bixpe-automation`

### Logs locales

Los logs se guardan en `./logs/` (si está configurado)

## 🐛 Troubleshooting

### Error: "Chromium not found"

```bash
docker build --no-cache -t bixpe-bot .
```

### Error: "Invalid Telegram token"

- Verifica que el token sea correcto
- Prueba: `curl https://api.telegram.org/bot<TOKEN>/getMe`

### Error: "Element not found"

- El HTML puede haber cambiado
- Inspecciona la web e actualiza los selectores en `main.py`
- Ejecuta localmente con `HEADLESS=false` para ver qué pasa

### Container se reinicia constantemente

- Revisa los logs: `docker logs bixpe-automation`
- Verifica que las credenciales sean correctas
- Confirma que Telegram esté configurado

## 📁 Estructura de archivos

```
autoBixpe/
├── main.py              # Script principal
├── requirements.txt     # Dependencias Python
├── Dockerfile          # Imagen Docker
├── docker-compose.yml  # Orquestación Docker
├── .env.example        # Variables de ejemplo
├── .env                # Variables (NO commitear)
├── .gitignore          # Archivos a ignorar en Git
├── README.md           # Este archivo
├── logs/               # Directorio de logs
└── screenshots/        # Capturas (temporal)
```

## 🔐 Seguridad

⚠️ **IMPORTANTE:**
- **NO subir `.env` a GitHub** - Contiene credenciales
- Usa `Secrets` en Portainer para variables sensibles
- Cambia las contraseñas regularmente
- No comparte tokens de Telegram

## 🌐 Publicar en Docker Hub (Opcional)

```bash
docker login
docker build -t tu-usuario/autobixpe:latest .
docker push tu-usuario/autobixpe:latest
```

Luego en Portainer puedes usar `tu-usuario/autobixpe:latest`

## 📝 Notas

- El bot detecta automáticamente si está más cerca de las 9:00 o 18:00
- Se ejecuta una sola vez por inicio
- Compatible con cualquier versión de Bixpe que use los selectores HTML actuales
- Las capturas se envían automáticamente por Telegram

## 🤝 Contribuciones

Si encuentras bugs o mejoras, siéntete libre de hacer un pull request.

## 📄 Licencia

MIT

## 📞 Soporte

Para reportar problemas, abre un issue en GitHub.

---

**Última actualización:** Enero 2026  
**Versión:** 1.0.0

