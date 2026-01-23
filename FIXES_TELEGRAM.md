# Solución de Problemas de Notificaciones Telegram

## Problemas Identificados

Los errores en los logs se debían a:

### 1. **`RuntimeError('Event loop is closed')`**
   - **Causa**: Estabas usando `asyncio.run()` en las funciones síncronas (`morning_task_sync()` y `afternoon_task_sync()`)
   - **Problema**: `asyncio.run()` crea un nuevo event loop y lo destruye al terminar
   - Cuando se completaban las tareas, el loop quedaba cerrado, y las notificaciones finales (enviadas por Telegram) intentaban usar un loop inexistente
   
### 2. **`Pool timeout: All connections in the connection pool are occupied`**
   - **Causa**: No había configuración explícita del pool de conexiones de `python-telegram-bot`
   - **Problema**: El pool por defecto es pequeño y se saturaba con múltiples solicitudes simultáneas
   - Las conexiones HTTP no se reutilizaban adecuadamente

### 3. **Scheduler incompatible con AsyncIO**
   - **Causa**: Usabas `BackgroundScheduler` que ejecuta en thread separado
   - **Problema**: Creaba conflictos entre threads cuando intentaba acceder al event loop

## Soluciones Implementadas

### 1. **Cambio a AsyncIOScheduler**
```python
# Antes:
from apscheduler.schedulers.background import BackgroundScheduler
scheduler = BackgroundScheduler()

# Ahora:
from apscheduler.schedulers.asyncio import AsyncIOScheduler
scheduler = AsyncIOScheduler()
scheduler.start()
scheduler.configure(event_loop=event_loop)
```

### 2. **Loop Global Reutilizable**
```python
# Se agregó variable global para el event loop
event_loop = None

# En main():
global event_loop
event_loop = asyncio.get_event_loop()
```

### 3. **Tareas Ejecutadas en Loop Global**
```python
# Antes:
def morning_task_sync() -> None:
    if bot_state["running"]:
        asyncio.run(morning_task())  # ❌ Crea nuevo loop

# Ahora:
def morning_task_sync() -> None:
    if bot_state["running"] and event_loop:
        asyncio.run_coroutine_threadsafe(morning_task(), event_loop)  # ✅ Usa loop global
```

### 4. **Pool de Conexiones Optimizado**
```python
# Nuevo bot con configuración de pool:
telegram_bot = Bot(
    token=TELEGRAM_TOKEN,
    request=aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(
            limit=5,              # Total de conexiones
            limit_per_host=5,     # Por host
            ttl_dns_cache=300     # Cache DNS
        ),
        timeout=aiohttp.ClientTimeout(total=10)
    )
)
```

### 5. **Reintentos Exponenciales**
```python
# La función send_telegram_notification() ahora:
# - Reintenta hasta 3 veces con backoff exponencial (1s, 2s, 4s)
# - Evita fallos ocasionales por timeout
```

### 6. **Dependencia Agregada**
```
aiohttp==3.9.1
```

## Archivos Modificados

- ✅ `main.py` - Refactorizado con AsyncIOScheduler y pool de conexiones
- ✅ `requirements.txt` - Agregada dependencia `aiohttp`

## Pruebas Recomendadas

1. **Verifica los logs en la próxima ejecución de tareas** para confirmar que no aparecen los errores de pool timeout
2. **Observa si las notificaciones llegan correctamente** sin el error `Event loop is closed`
3. **Monitorea el consumo de conexiones** - debería estar más estable

## Ventajas de estos Cambios

✅ **No más "Event loop is closed"** - El loop se mantiene durante toda la ejecución  
✅ **Pool de conexiones correctamente gestionado** - Conexiones reutilizables  
✅ **Mejor compatibilidad AsyncIO** - Scheduler y bot en el mismo contexto async  
✅ **Reintentos automáticos** - Las notificaciones son más robustas  
✅ **Mejor manejo de concurrencia** - Sin conflictos thread/async  

## Próximos Pasos

Si aún experimentes problemas:
1. Ajusta `TELEGRAM_POOL_SIZE` (actualmente 5) en `main.py` según carga
2. Aumenta `TELEGRAM_POOL_TIMEOUT` (actualmente 10s) si hay timeouts frecuentes
3. Revisa que el token y chat ID de Telegram sean correctos en `.env`
