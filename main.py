import asyncio
import os
from datetime import datetime
from playwright.async_api import async_playwright
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import signal
import sys
from concurrent.futures import ThreadPoolExecutor
import aiohttp

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuración desde variables de entorno
LOGIN_URL = "https://auth2.bixpe.com/Account/Login"
USERNAME = os.getenv("BIXPE_USERNAME", "tu_usuario")
PASSWORD = os.getenv("BIXPE_PASSWORD", "tu_contraseña")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
BUTTON_SELECTOR = os.getenv("BUTTON_SELECTOR", "button[type='submit']")  # Ajusta según la web
HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"

# Configuración del pool de conexiones
TELEGRAM_POOL_SIZE = 5
TELEGRAM_POOL_TIMEOUT = 10

# Instancia del bot de Telegram (se inicializa en main usando la Application)
telegram_bot = None

# Scheduler global (AsyncIOScheduler en lugar de BackgroundScheduler)
scheduler = None

# Loop global
event_loop = None

# Estado del bot
bot_state = {
    "running": True,
    "app": None
}

async def send_telegram_notification(message: str, is_error: bool = False) -> None:
    """Envía notificación por Telegram con reintentos"""
    if not telegram_bot or not TELEGRAM_CHAT_ID:
        logger.warning("⚠️ Telegram no configurado")
        return

    max_retries = 3
    for attempt in range(max_retries):
        try:
            emoji = "❌" if is_error else "✅"
            full_message = f"{emoji} {message}\n\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            await telegram_bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=full_message,
                parse_mode="HTML"
            )
            logger.info(f"📱 Notificación enviada por Telegram")
            return
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Backoff exponencial: 1s, 2s, 4s
                logger.warning(f"⚠️ Intento {attempt + 1} fallido al enviar notificación, reintentando en {wait_time}s: {e}")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"❌ Error al enviar notificación Telegram (después de {max_retries} intentos): {e}")


async def validate_telegram_connection() -> bool:
    """Valida que la conexión de Telegram siga siendo válida"""
    if not telegram_bot:
        logger.warning("⚠️ Bot de Telegram no inicializado")
        return False

    try:
        me = await telegram_bot.get_me()
        logger.info(f"✅ Conexión de Telegram validada: @{me.username}")
        return True
    except Exception as e:
        logger.error(f"❌ Conexión de Telegram inválida: {e}")
        return False


async def handle_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja comando /start para reanudar el bot"""
    global scheduler, bot_state, telegram_bot, event_loop

    try:
        if not bot_state["running"]:
            logger.info("🔄 Intentando reanudar el bot...")

            # Validar que el event loop sigue siendo válido
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                logger.error("❌ Event loop no válido, recreando...")
                event_loop = asyncio.get_event_loop()

            bot_state["running"] = True

            # Reiniciar scheduler si está detenido
            if scheduler:
                if scheduler.running:
                    scheduler.resume()
                    logger.info("✅ Scheduler reanudado")
                else:
                    scheduler.start()
                    logger.info("✅ Scheduler iniciado")

            # Validar conexión de Telegram
            if telegram_bot:
                try:
                    me = await telegram_bot.get_me()
                    logger.info(f"✅ Bot de Telegram validado: {me.username}")
                except Exception as tg_error:
                    logger.warning(f"⚠️ Token de Telegram inválido o expirado: {tg_error}")
                    await update.message.reply_text(
                        "⚠️ <b>Error:</b> Conexión de Telegram inválida\n"
                        "Reinicia el contenedor para recargarlo.",
                        parse_mode="HTML"
                    )
                    bot_state["running"] = False
                    return

            logger.info("▶️ BOT REANUDADO POR COMANDO TELEGRAM")
            await update.message.reply_text(
                "▶️ <b>Bot reanudado</b>\n\n"
                "Las tareas se ejecutarán de Lunes a Viernes:\n"
                "• 09:00 - Login + Fichaje\n"
                "• 18:00 - Finalizar jornada",
                parse_mode="HTML"
            )
            await send_telegram_notification("▶️ <b>Bot REANUDADO</b> - Tareas programadas activas (L-V)")
        else:
            await update.message.reply_text(
                "✅ Bot ya está <b>activo</b>\n\n"
                "Próximas tareas (Lunes a Viernes):\n"
                "• 09:00 - Login + Fichaje\n"
                "• 18:00 - Finalizar jornada",
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"❌ Error en comando /start: {e}")
        bot_state["running"] = False
        await update.message.reply_text(f"❌ Error: {str(e)}", parse_mode="HTML")

async def handle_stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja comando /stop para pausar el bot"""
    global scheduler, bot_state

    try:
        if bot_state["running"]:
            bot_state["running"] = False

            # Pausar scheduler
            if scheduler and scheduler.running:
                scheduler.pause()
                logger.info("⏸️ Scheduler pausado")

            logger.info("⏸️ BOT PAUSADO POR COMANDO TELEGRAM")
            await update.message.reply_text(
                "⏸️ <b>Bot pausado</b>\n\n"
                "Las tareas programadas están pausadas.\n"
                "Usa /start para reanudar.",
                parse_mode="HTML"
            )
            await send_telegram_notification("⏸️ <b>Bot PAUSADO</b> - Las tareas están suspendidas")
        else:
            await update.message.reply_text(
                "⏸️ Bot ya está <b>pausado</b>\n\n"
                "Usa /start para reanudar.",
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"❌ Error en comando /stop: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}", parse_mode="HTML")

async def handle_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja comando /status para ver estado del bot"""
    try:
        status = "▶️ ACTIVO" if bot_state["running"] else "⏸️ PAUSADO"
        scheduler_status = "✅ Funcionando" if scheduler and scheduler.running else "❌ Detenido"
        
        await update.message.reply_text(
            f"<b>Estado del Bot Bixpe</b>\n\n"
            f"Estado general: {status}\n"
            f"Scheduler: {scheduler_status}\n\n"
            f"<b>Comandos disponibles:</b>\n"
            f"/start - Reanudar bot\n"
            f"/stop - Pausar bot\n"
            f"/status - Ver estado",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"❌ Error en comando /status: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}", parse_mode="HTML")


async def take_screenshot_and_send(page, event_name: str) -> None:
    """Toma una captura de pantalla y la envía por Telegram"""
    try:
        import tempfile
        import platform
        
        # Crear ruta según el SO
        if platform.system() == "Windows":
            screenshot_path = os.path.join(tempfile.gettempdir(), f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        else:
            screenshot_path = f"/tmp/screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        
        await page.screenshot(path=screenshot_path)
        logger.info(f"📸 Captura guardada: {screenshot_path}")
        
        if telegram_bot and TELEGRAM_CHAT_ID:
            try:
                with open(screenshot_path, 'rb') as photo:
                    await telegram_bot.send_photo(
                        chat_id=TELEGRAM_CHAT_ID,
                        photo=photo,
                        caption=f"🔔 {event_name}\nTiempo: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                logger.info(f"✅ Captura enviada por Telegram: {event_name}")
            except Exception as tg_error:
                logger.error(f"❌ Error al enviar a Telegram: {tg_error}")
        else:
            if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
                logger.warning("⚠️ Telegram no configurado (ejecutando sin envío de capturas)")
            
        # Eliminar archivo temporal
        if os.path.exists(screenshot_path):
            os.remove(screenshot_path)
            
    except Exception as e:
        logger.error(f"❌ Error al tomar captura: {e}")

def morning_task_sync() -> None:
    """Wrapper síncrono para la tarea de la mañana - Ejecuta en el loop global"""
    if bot_state["running"] and event_loop and not event_loop.is_closed():
        try:
            asyncio.run_coroutine_threadsafe(morning_task(), event_loop)
        except Exception as e:
            logger.error(f"❌ Error al encolar tarea de mañana: {e}")
    else:
        logger.warning("⏸️ Tarea de mañana saltada - Bot pausado o loop inválido")

async def morning_task() -> None:
    """Tarea de las 9:00 - Login y click en botón"""
    async with async_playwright() as p:
        try:
            logger.info("=" * 50)
            logger.info("🌅 INICIANDO TAREA DE MAÑANA (9:00)")
            logger.info("=" * 50)
            await send_telegram_notification("🌅 Iniciando tarea de MAÑANA (9:00) - Login y fichaje")
            
            # Lanzar navegador
            logger.info("🚀 Lanzando navegador Chrome...")
            browser = await p.chromium.launch(headless=HEADLESS)
            context = await browser.new_context()
            page = await context.new_page()
            
            logger.info("🌐 Navegando a la página de login...")
            await page.goto(LOGIN_URL, wait_until="networkidle")
            
            # Hacer login
            logger.info("🔐 Ingresando credenciales...")
            await page.fill("input#Username", USERNAME)
            await page.fill("input#Password", PASSWORD)
            
            # Esperar y hacer clic en el botón de login
            logger.info("🔘 Haciendo clic en botón de login...")
            await page.click("button[type='submit']")
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)
            
            logger.info("✅ Login completado")
            
            # Enviar captura tras login
            await take_screenshot_and_send(page, "✅ Login Exitoso - TAREA MAÑANA (9:00)")
            
            # Esperar antes de hacer clic en el siguiente botón
            logger.info("⏳ Esperando 3 segundos antes de hacer clic en el botón de START...")
            await asyncio.sleep(3)
            
            # Buscar y hacer clic en el botón de inicio
            logger.info("🔍 Buscando botón de START...")
            start_button = await page.query_selector("button#btn-start-workday")
            if start_button:
                await start_button.click()
                logger.info("▶️ Botón START clickeado")
                await asyncio.sleep(2)
                
                # Esperar a que aparezca el popup de confirmación
                logger.info("⏳ Esperando popup de confirmación...")
                try:
                    confirm_button = await page.wait_for_selector("button.swal2-confirm.swal2-styled", timeout=5000)
                    await confirm_button.click()
                    logger.info("✅ Popup confirmado - Inicio de jornada confirmado")
                    await asyncio.sleep(2)
                except:
                    logger.warning("⚠️ Popup no encontrado, continuando...")
                
                await take_screenshot_and_send(page, "▶️ Botón START y confirmación completados (9:00)")
            else:
                logger.warning("⚠️ Botón START no encontrado")
            
            await browser.close()
            logger.info("🏁 TAREA DE MAÑANA COMPLETADA\n")
            await send_telegram_notification("✅ Tarea de MAÑANA completada exitosamente", is_error=False)
            
        except Exception as e:
            logger.error(f"❌ Error en tarea de mañana: {e}", exc_info=True)
            await send_telegram_notification(f"<b>❌ ERROR en tarea MAÑANA:</b>\n<code>{str(e)}</code>", is_error=True)

def afternoon_task_sync() -> None:
    """Wrapper síncrono para la tarea de la tarde - Ejecuta en el loop global"""
    if bot_state["running"] and event_loop and not event_loop.is_closed():
        try:
            asyncio.run_coroutine_threadsafe(afternoon_task(), event_loop)
        except Exception as e:
            logger.error(f"❌ Error al encolar tarea de tarde: {e}")
    else:
        logger.warning("⏸️ Tarea de tarde saltada - Bot pausado o loop inválido")


async def afternoon_task() -> None:
    """Tarea de las 18:00 - Login y click en botón de stop"""
    async with async_playwright() as p:
        try:
            logger.info("=" * 50)
            logger.info("🌆 INICIANDO TAREA DE TARDE (18:00)")
            logger.info("=" * 50)
            await send_telegram_notification("🌆 Iniciando tarea de TARDE (18:00) - Finalizar jornada")
            
            # Lanzar navegador
            logger.info("🚀 Lanzando navegador Chrome...")
            browser = await p.chromium.launch(headless=HEADLESS)
            context = await browser.new_context()
            page = await context.new_page()
            
            logger.info("🌐 Navegando a la página de login...")
            await page.goto(LOGIN_URL, wait_until="networkidle")
            
            # Hacer login
            logger.info("🔐 Ingresando credenciales...")
            await page.fill("input#Username", USERNAME)
            await page.fill("input#Password", PASSWORD)
            
            # Esperar y hacer clic en el botón de login
            logger.info("🔘 Haciendo clic en botón de login...")
            await page.click("button[type='submit']")
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)
            
            logger.info("✅ Login completado")
            
            # Enviar captura tras login
            await take_screenshot_and_send(page, "✅ Login Exitoso - TAREA TARDE (18:00)")
            
            # Esperar antes de hacer clic
            logger.info("⏳ Esperando 3 segundos antes de hacer clic en el botón de STOP...")
            await asyncio.sleep(3)
            
            # Buscar y hacer clic en el botón de stop
            logger.info("🔍 Buscando botón de STOP...")
            stop_button = await page.query_selector("button#btn-stop-workday")
            if stop_button:
                await stop_button.click()
                logger.info("⏹️ Botón STOP clickeado")
                await asyncio.sleep(2)
                
                # Esperar a que aparezca el popup de confirmación
                logger.info("⏳ Esperando popup de confirmación...")
                try:
                    confirm_button = await page.wait_for_selector("button.swal2-confirm.swal2-styled", timeout=5000)
                    await confirm_button.click()
                    logger.info("✅ Popup confirmado - 'Sí, finalizar mi jornada' clickeado")
                    await asyncio.sleep(2)
                except Exception:
                    logger.warning("⚠️ Popup no encontrado, continuando...")
                
                await take_screenshot_and_send(page, "⏹️ Botón STOP y confirmación completados (18:00)")
            else:
                logger.warning("⚠️ Botón STOP no encontrado")
            
            await browser.close()
            logger.info("🏁 TAREA DE TARDE COMPLETADA\n")
            await send_telegram_notification("✅ Tarea de TARDE completada exitosamente", is_error=False)
            
        except Exception as e:
            logger.error(f"❌ Error en tarea de tarde: {e}", exc_info=True)
            await send_telegram_notification(f"<b>❌ ERROR en tarea TARDE:</b>\n<code>{str(e)}</code>", is_error=True)


def shutdown_scheduler(signum, frame) -> None:
    """Maneja el cierre graceful del scheduler"""
    logger.info("\n🛑 Señal de cierre recibida...")
    if scheduler and scheduler.running:
        scheduler.shutdown()
        logger.info("✅ Scheduler detenido")
    sys.exit(0)


def init_scheduler() -> None:
    """Inicializa el scheduler de tareas"""
    global scheduler
    
    # Usar AsyncIOScheduler en lugar de BackgroundScheduler
    scheduler = AsyncIOScheduler()
    tz = pytz.timezone('Europe/Madrid')
    
    # Programar tarea de mañana a las 9:00
    scheduler.add_job(
        morning_task_sync,
        CronTrigger(day_of_week='mon-fri', hour=9, minute=0, second=0, timezone=tz),
        id='morning_task',
        name='Tarea Mañana (9:00, L-V)',
        replace_existing=True,
        misfire_grace_time=60
    )
    
    # Programar tarea de tarde a las 18:00
    scheduler.add_job(
        afternoon_task_sync,
        CronTrigger(day_of_week='mon-fri', hour=18, minute=0, second=0, timezone=tz),
        id='afternoon_task',
        name='Tarea Tarde (18:00, L-V)',
        replace_existing=True,
        misfire_grace_time=60
    )
    
    # scheduler.start()  <-- Se elimina de aquí, se inicia en main
    logger.info("✅ Scheduler configurado correctamente")
    logger.info("📅 Tareas programadas (Lunes a Viernes):")
    logger.info("   • 09:00 - Tarea de MAÑANA (Login + Fichaje)")
    logger.info("   • 18:00 - Tarea de TARDE (Stop + Finalizar jornada)")


async def init_telegram_handlers():
    """Inicializa los handlers de comandos de Telegram"""
    if not TELEGRAM_TOKEN:
        logger.warning("⚠️ TELEGRAM_TOKEN no configurado - Comandos deshabilitados")
        return None
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Agregar handlers de comandos
    app.add_handler(CommandHandler("start", handle_start_command))
    app.add_handler(CommandHandler("stop", handle_stop_command))
    app.add_handler(CommandHandler("status", handle_status_command))
    
    bot_state["app"] = app
    
    logger.info("✅ Handlers de Telegram inicializados")
    logger.info("📱 Comandos disponibles:")
    logger.info("   • /start - Reanudar bot")
    logger.info("   • /stop - Pausar bot")
    logger.info("   • /status - Ver estado")
    
    return app


async def main() -> None:
    """Función principal - mantiene el bot corriendo 24/7"""
    global event_loop, scheduler, telegram_bot, bot_state
    event_loop = asyncio.get_event_loop()

    logger.info("\n" + "🤖 " * 20)
    logger.info("INICIALIZANDO BOT DE BIXPE - MODO 24/7 CON TELEGRAM")
    logger.info("🤖 " * 20 + "\n")

    logger.info(f"📌 Usuario: {USERNAME}")
    logger.info(f"🔗 URL: {LOGIN_URL}")
    logger.info(f"👁️ Headless: {HEADLESS}\n")

    # Registrar manejadores de señales para cierre graceful
    signal.signal(signal.SIGINT, shutdown_scheduler)
    signal.signal(signal.SIGTERM, shutdown_scheduler)

    # Inicializar scheduler (configuración de jobs)
    init_scheduler()

    # Inicializar handlers de Telegram
    app = await init_telegram_handlers()

    # Vincular el bot de la aplicación a la variable global
    if app:
        telegram_bot = app.bot

    # Iniciar el scheduler explícitamente dentro del loop principal
    if scheduler and not scheduler.running:
        scheduler.start()
        logger.info("✅ Scheduler iniciado")

    try:
        await send_telegram_notification("🤖 <b>Bot iniciado - Modo 24/7 activado</b>\n\n📅 Próximas tareas (Lunes a Viernes):\n• 09:00 - Login + Fichaje\n• 18:00 - Finalizar jornada\n\n📱 Usa: /start /stop /status")
        logger.info("🌐 Bot en modo 24/7, esperando próxima tarea...\n")

        # Iniciar polling de Telegram si está configurado
        if app:
            logger.info("📱 Iniciando polling de Telegram...")
            await app.initialize()
            await app.start()
            await app.updater.start_polling()
            logger.info("✅ Polling de Telegram iniciado\n")

        # Validación periódica de conexión (cada 5 minutos)
        last_validation = datetime.now()
        validation_interval = 300  # 5 minutos

        # Mantener el bot corriendo indefinidamente
        while True:
            await asyncio.sleep(60)

            # Validar conexión de Telegram cada 5 minutos
            now = datetime.now()
            if (now - last_validation).total_seconds() > validation_interval:
                if bot_state["running"] and app:
                    is_valid = await validate_telegram_connection()
                    if not is_valid:
                        logger.warning("⚠️ Conexión de Telegram inválida, pero polling sigue activo")
                last_validation = now

    except KeyboardInterrupt:
        logger.info("\n🛑 Bot detenido por el usuario")
        if app:
            await app.updater.stop()
            await app.stop()
            await app.shutdown()
        if scheduler and scheduler.running:
            scheduler.shutdown()
    except Exception as e:
        logger.error(f"\n❌ Error fatal: {e}", exc_info=True)
        await send_telegram_notification(f"<b>❌ ERROR FATAL EN BOT:</b>\n<code>{str(e)}</code>", is_error=True)
        if app:
            try:
                await app.updater.stop()
                await app.stop()
                await app.shutdown()
            except Exception:
                pass
        if scheduler and scheduler.running:
            scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
