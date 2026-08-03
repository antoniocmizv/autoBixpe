import asyncio
import os
from datetime import datetime, date
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
import json
from pathlib import Path

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

# Ruta de archivos de configuración
VACACIONES_FILE = "vacaciones.json"
JORNADA_FILE = "jornada.json"

# Configuración del pool de conexiones
TELEGRAM_POOL_SIZE = 5
TELEGRAM_POOL_TIMEOUT = 10

# Horas de trabajo
WORKDAY_8_START = 9
WORKDAY_8_END = 18
WORKDAY_7_START = 9
WORKDAY_7_END = 17

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


def load_vacaciones() -> list:
    """Carga las vacaciones desde el archivo JSON"""
    try:
        if Path(VACACIONES_FILE).exists():
            with open(VACACIONES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('vacaciones', [])
    except Exception as e:
        logger.warning(f"⚠️ Error al cargar vacaciones: {e}")
    return []


def save_vacaciones(vacaciones: list) -> None:
    """Guarda las vacaciones en el archivo JSON"""
    try:
        with open(VACACIONES_FILE, 'w', encoding='utf-8') as f:
            json.dump({'vacaciones': vacaciones}, f, indent=2, ensure_ascii=False)
        logger.info("✅ Vacaciones guardadas")
    except Exception as e:
        logger.error(f"❌ Error al guardar vacaciones: {e}")


def load_jornada() -> dict:
    """Carga la configuración de jornada desde el archivo JSON"""
    try:
        if Path(JORNADA_FILE).exists():
            with open(JORNADA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('jornada', {'horas': 8, 'entrada': WORKDAY_8_START, 'salida': WORKDAY_8_END})
    except Exception as e:
        logger.warning(f"⚠️ Error al cargar jornada: {e}")
    return {'horas': 8, 'entrada': WORKDAY_8_START, 'salida': WORKDAY_8_END}


def save_jornada(jornada: dict) -> None:
    """Guarda la configuración de jornada en el archivo JSON"""
    try:
        with open(JORNADA_FILE, 'w', encoding='utf-8') as f:
            json.dump({'jornada': jornada}, f, indent=2, ensure_ascii=False)
        logger.info("✅ Jornada guardada")
    except Exception as e:
        logger.error(f"❌ Error al guardar jornada: {e}")


def is_vacation_today() -> bool:
    """Verifica si hoy es día de vacaciones"""
    vacaciones = load_vacaciones()
    today = date.today().isoformat()

    for v in vacaciones:
        try:
            inicio = datetime.strptime(v['fecha_inicio'], '%Y-%m-%d').date()
            fin = datetime.strptime(v['fecha_fin'], '%Y-%m-%d').date()

            if inicio <= date.today() <= fin:
                logger.info(f"🏖️ HOY ES VACACIONES: {v.get('razon', 'Sin descripción')}")
                return True
        except Exception as e:
            logger.warning(f"⚠️ Error al procesar vacación: {e}")

    return False

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
        jornada = load_jornada()
        salida = jornada['salida']

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
                f"▶️ <b>Bot reanudado</b>\n\n"
                f"Las tareas se ejecutarán de Lunes a Viernes:\n"
                f"• 09:00 - Login + Fichaje\n"
                f"• {salida:02d}:00 - Finalizar jornada de {jornada['horas']}h",
                parse_mode="HTML"
            )
            await send_telegram_notification(f"▶️ <b>Bot REANUDADO</b> - Tareas: 09:00-{salida:02d}:00 ({jornada['horas']}h, L-V)")
        else:
            await update.message.reply_text(
                f"✅ Bot ya está <b>activo</b>\n\n"
                f"Próximas tareas (Lunes a Viernes):\n"
                f"• 09:00 - Login + Fichaje\n"
                f"• {salida:02d}:00 - Finalizar jornada de {jornada['horas']}h",
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
        jornada = load_jornada()

        await update.message.reply_text(
            f"<b>📊 Estado del Bot Bixpe</b>\n\n"
            f"🔴 Estado general: {status}\n"
            f"⚙️ Scheduler: {scheduler_status}\n"
            f"⏰ Jornada: {jornada['horas']}h ({jornada['entrada']:02d}:00 - {jornada['salida']:02d}:00)\n\n"
            f"<b>📋 Comandos disponibles:</b>\n"
            f"<b>Control:</b>\n"
            f"  /start - Reanudar bot\n"
            f"  /stop - Pausar bot\n"
            f"<b>Jornada:</b>\n"
            f"  /workday - Ver jornada actual\n"
            f"  /workday_set 7|8 - Cambiar a 7h u 8h\n"
            f"<b>Vacaciones:</b>\n"
            f"  /vacation INICIO FIN [RAZÓN] - Agregar\n"
            f"  /vacation_list - Ver todas\n"
            f"  /vacation_delete ID - Eliminar",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"❌ Error en comando /status: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}", parse_mode="HTML")


async def handle_workday_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra la jornada actual"""
    try:
        jornada = load_jornada()
        await update.message.reply_text(
            f"<b>📅 Jornada Actual</b>\n\n"
            f"Horas: <b>{jornada['horas']}h</b>\n"
            f"Entrada: {jornada['entrada']:02d}:00\n"
            f"Salida: {jornada['salida']:02d}:00\n\n"
            f"Usa /workday_set 7 ó /workday_set 8 para cambiar",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"❌ Error en comando /workday: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}", parse_mode="HTML")


async def handle_workday_set_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cambia la jornada de trabajo"""
    try:
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text(
                "❌ Formato incorrecto\n\n"
                "<b>Uso:</b> /workday_set HORAS\n\n"
                "<b>Ejemplos:</b>\n"
                "/workday_set 8 - Jornada de 8 horas (09:00-18:00)\n"
                "/workday_set 7 - Jornada de 7 horas (09:00-16:00)",
                parse_mode="HTML"
            )
            return

        horas = int(context.args[0])

        if horas == 8:
            jornada = {'horas': 8, 'entrada': WORKDAY_8_START, 'salida': WORKDAY_8_END}
        elif horas == 7:
            jornada = {'horas': 7, 'entrada': WORKDAY_7_START, 'salida': WORKDAY_7_END}
        else:
            await update.message.reply_text("❌ Solo se permiten 7 u 8 horas", parse_mode="HTML")
            return

        save_jornada(jornada)
        await update.message.reply_text(
            f"✅ <b>Jornada actualizada</b>\n\n"
            f"Horas: {jornada['horas']}h\n"
            f"Entrada: {jornada['entrada']:02d}:00\n"
            f"Salida: {jornada['salida']:02d}:00",
            parse_mode="HTML"
        )
        logger.info(f"🔄 Jornada cambiada a {jornada['horas']}h")
        await send_telegram_notification(f"🔄 Jornada actualizada: <b>{jornada['horas']}h</b> ({jornada['entrada']:02d}:00 - {jornada['salida']:02d}:00)")

    except Exception as e:
        logger.error(f"❌ Error en comando /workday_set: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}", parse_mode="HTML")


async def handle_vacation_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja comando /vacation para agregar vacaciones"""
    try:
        if len(context.args) < 2:
            await update.message.reply_text(
                "❌ Formato incorrecto\n\n"
                "<b>Uso:</b> /vacation FECHA_INICIO FECHA_FIN [RAZÓN]\n\n"
                "<b>Ejemplo:</b> /vacation 2026-05-15 2026-05-22 Vacaciones en playa\n\n"
                "Fechas en formato: YYYY-MM-DD",
                parse_mode="HTML"
            )
            return

        fecha_inicio = context.args[0]
        fecha_fin = context.args[1]
        razon = " ".join(context.args[2:]) if len(context.args) > 2 else "Sin descripción"

        # Validar formato de fechas
        try:
            inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d')
            fin = datetime.strptime(fecha_fin, '%Y-%m-%d')

            if inicio > fin:
                await update.message.reply_text("❌ La fecha de inicio no puede ser mayor que la fecha de fin", parse_mode="HTML")
                return

            if inicio < datetime.now():
                await update.message.reply_text("❌ La fecha de inicio no puede ser en el pasado", parse_mode="HTML")
                return

        except ValueError:
            await update.message.reply_text("❌ Formato de fecha inválido. Usa: YYYY-MM-DD", parse_mode="HTML")
            return

        # Agregar vacación
        vacaciones = load_vacaciones()
        nueva_vacacion = {
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "razon": razon,
            "agregada": datetime.now().isoformat()
        }
        vacaciones.append(nueva_vacacion)
        save_vacaciones(vacaciones)

        dias = (fin - inicio).days + 1
        await update.message.reply_text(
            f"✅ <b>Vacación agregada</b>\n\n"
            f"📅 Desde: {fecha_inicio}\n"
            f"📅 Hasta: {fecha_fin}\n"
            f"📝 Descripción: {razon}\n"
            f"⏳ Duración: {dias} días\n\n"
            f"⚠️ <b>El bot NO ejecutará tareas durante estos días.</b>",
            parse_mode="HTML"
        )
        logger.info(f"🏖️ Vacación agregada: {fecha_inicio} a {fecha_fin}")
        await send_telegram_notification(f"🏖️ Vacaciones agregadas: {fecha_inicio} a {fecha_fin} ({razon})")

    except Exception as e:
        logger.error(f"❌ Error en comando /vacation: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}", parse_mode="HTML")


async def handle_vacation_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra la lista de vacaciones"""
    try:
        vacaciones = load_vacaciones()

        if not vacaciones:
            await update.message.reply_text("✅ No hay vacaciones programadas", parse_mode="HTML")
            return

        mensaje = "<b>📅 Vacaciones Programadas</b>\n\n"
        for idx, v in enumerate(vacaciones, 1):
            try:
                inicio = datetime.strptime(v['fecha_inicio'], '%Y-%m-%d').date()
                fin = datetime.strptime(v['fecha_fin'], '%Y-%m-%d').date()
                dias = (fin - inicio).days + 1
                estado = "🟢 ACTIVA" if inicio <= date.today() <= fin else "⚪ FUTURA"

                mensaje += f"<b>{idx}.</b> {estado}\n"
                mensaje += f"   📅 {v['fecha_inicio']} → {v['fecha_fin']} ({dias} días)\n"
                mensaje += f"   📝 {v['razon']}\n\n"
            except Exception:
                pass

        mensaje += "<b>Usar:</b> /vacation_delete ID"
        await update.message.reply_text(mensaje, parse_mode="HTML")

    except Exception as e:
        logger.error(f"❌ Error en comando /vacation_list: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}", parse_mode="HTML")


async def handle_vacation_delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Elimina una vacación"""
    try:
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text(
                "❌ Uso: /vacation_delete ID\n\n"
                "Usa /vacation_list para ver los IDs",
                parse_mode="HTML"
            )
            return

        idx = int(context.args[0]) - 1
        vacaciones = load_vacaciones()

        if idx < 0 or idx >= len(vacaciones):
            await update.message.reply_text("❌ ID de vacación inválido", parse_mode="HTML")
            return

        vacacion_eliminada = vacaciones.pop(idx)
        save_vacaciones(vacaciones)

        await update.message.reply_text(
            f"✅ <b>Vacación eliminada</b>\n\n"
            f"📅 {vacacion_eliminada['fecha_inicio']} → {vacacion_eliminada['fecha_fin']}\n"
            f"📝 {vacacion_eliminada['razon']}",
            parse_mode="HTML"
        )
        logger.info(f"🗑️ Vacación eliminada: {vacacion_eliminada['fecha_inicio']}")

    except Exception as e:
        logger.error(f"❌ Error en comando /vacation_delete: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}", parse_mode="HTML")


async def login_to_bixpe(page) -> bool:
    """Realiza login en Bixpe y retorna True si es exitoso"""
    try:
        logger.info("🌐 Navegando a la página de login...")
        await page.goto(LOGIN_URL, wait_until="networkidle")

        if not USERNAME or not PASSWORD:
            logger.error("❌ USERNAME o PASSWORD no configurados")
            return False

        logger.info("🔐 Ingresando credenciales...")
        await page.fill("input#Username", USERNAME)
        await page.fill("input#Password", PASSWORD)

        logger.info("🔘 Haciendo clic en botón de login...")
        await page.click("button[type='submit']")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)

        logger.info("✅ Login completado")
        return True
    except Exception as e:
        logger.error(f"❌ Error durante login: {e}")
        return False


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
    if is_vacation_today():
        logger.info("🏖️ Tarea de mañana cancelada - HOY ES VACACIONES")
        return

    if bot_state["running"] and event_loop and not event_loop.is_closed():
        try:
            asyncio.run_coroutine_threadsafe(morning_task(), event_loop)
        except Exception as e:
            logger.error(f"❌ Error al encolar tarea de mañana: {e}")
    else:
        logger.warning("⏸️ Tarea de mañana saltada - Bot pausado o loop inválido")

async def morning_task() -> None:
    """Tarea de las 9:00 - Login y click en botón START"""
    async with async_playwright() as p:
        browser = None
        try:
            logger.info("=" * 50)
            logger.info("🌅 INICIANDO TAREA DE MAÑANA (9:00)")
            logger.info("=" * 50)
            await send_telegram_notification("🌅 Iniciando tarea de MAÑANA (9:00) - Login y fichaje")

            logger.info("🚀 Lanzando navegador Chrome...")
            browser = await p.chromium.launch(headless=HEADLESS)
            context = await browser.new_context()
            page = await context.new_page()

            if not await login_to_bixpe(page):
                await send_telegram_notification("<b>❌ ERROR en login MAÑANA</b>", is_error=True)
                return

            await take_screenshot_and_send(page, "✅ Login Exitoso - TAREA MAÑANA (9:00)")

            logger.info("⏳ Esperando 3 segundos antes de hacer clic en el botón de START...")
            await asyncio.sleep(3)

            logger.info("🔍 Buscando botón de START...")
            start_button = await page.query_selector("button#btn-start-workday")
            if start_button:
                await start_button.click()
                logger.info("▶️ Botón START clickeado")
                await asyncio.sleep(2)

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

            logger.info("🏁 TAREA DE MAÑANA COMPLETADA\n")
            await send_telegram_notification("✅ Tarea de MAÑANA completada exitosamente", is_error=False)

        except Exception as e:
            logger.error(f"❌ Error en tarea de mañana: {e}", exc_info=True)
            await send_telegram_notification(f"<b>❌ ERROR en tarea MAÑANA:</b>\n<code>{str(e)}</code>", is_error=True)
        finally:
            if browser:
                await browser.close()

def afternoon_task_sync() -> None:
    """Wrapper síncrono para la tarea de la tarde - Ejecuta en el loop global"""
    if is_vacation_today():
        logger.info("🏖️ Tarea de tarde cancelada - HOY ES VACACIONES")
        return

    if bot_state["running"] and event_loop and not event_loop.is_closed():
        try:
            asyncio.run_coroutine_threadsafe(afternoon_task(), event_loop)
        except Exception as e:
            logger.error(f"❌ Error al encolar tarea de tarde: {e}")
    else:
        logger.warning("⏸️ Tarea de tarde saltada - Bot pausado o loop inválido")


async def afternoon_task() -> None:
    """Tarea de la tarde - Login y click en botón de STOP"""
    jornada = load_jornada()
    salida_hora = jornada['salida']
    hora_actual = datetime.now().hour

    if hora_actual != salida_hora:
        logger.info(f"⏭️ Tarea de tarde saltada - Jornada de {jornada['horas']}h termina a las {salida_hora:02d}:00, no a las {hora_actual:02d}:00")
        return

    async with async_playwright() as p:
        browser = None
        try:
            logger.info("=" * 50)
            logger.info(f"🌆 INICIANDO TAREA DE TARDE ({salida_hora:02d}:00) - JORNADA DE {jornada['horas']}H")
            logger.info("=" * 50)
            await send_telegram_notification(f"🌆 Iniciando tarea de TARDE ({salida_hora:02d}:00) - Finalizar jornada de {jornada['horas']}h")

            logger.info("🚀 Lanzando navegador Chrome...")
            browser = await p.chromium.launch(headless=HEADLESS)
            context = await browser.new_context()
            page = await context.new_page()

            if not await login_to_bixpe(page):
                await send_telegram_notification("<b>❌ ERROR en login TARDE</b>", is_error=True)
                return

            await take_screenshot_and_send(page, f"✅ Login Exitoso - TAREA TARDE ({salida_hora:02d}:00)")

            logger.info("⏳ Esperando 3 segundos antes de hacer clic en el botón de STOP...")
            await asyncio.sleep(3)

            logger.info("🔍 Buscando botón de STOP...")
            stop_button = await page.query_selector("button#btn-stop-workday")
            if stop_button:
                await stop_button.click()
                logger.info("⏹️ Botón STOP clickeado")
                await asyncio.sleep(2)

                logger.info("⏳ Esperando popup de confirmación...")
                try:
                    confirm_button = await page.wait_for_selector("button.swal2-confirm.swal2-styled", timeout=5000)
                    await confirm_button.click()
                    logger.info("✅ Popup confirmado - 'Sí, finalizar mi jornada' clickeado")
                    await asyncio.sleep(2)
                except Exception:
                    logger.warning("⚠️ Popup no encontrado, continuando...")

                await take_screenshot_and_send(page, f"⏹️ Botón STOP y confirmación completados ({salida_hora:02d}:00)")
            else:
                logger.warning("⚠️ Botón STOP no encontrado")

            logger.info("🏁 TAREA DE TARDE COMPLETADA\n")
            await send_telegram_notification("✅ Tarea de TARDE completada exitosamente", is_error=False)

        except Exception as e:
            logger.error(f"❌ Error en tarea de tarde: {e}", exc_info=True)
            await send_telegram_notification(f"<b>❌ ERROR en tarea TARDE:</b>\n<code>{str(e)}</code>", is_error=True)
        finally:
            if browser:
                await browser.close()


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

    # Programar tarea de tarde a las 17:00 (para jornada de 7h)
    scheduler.add_job(
        afternoon_task_sync,
        CronTrigger(day_of_week='mon-fri', hour=17, minute=0, second=0, timezone=tz),
        id='afternoon_task_7h',
        name='Tarea Tarde (17:00, L-V - 7h)',
        replace_existing=True,
        misfire_grace_time=60
    )

    # Programar tarea de tarde a las 18:00 (para jornada de 8h)
    scheduler.add_job(
        afternoon_task_sync,
        CronTrigger(day_of_week='mon-fri', hour=18, minute=0, second=0, timezone=tz),
        id='afternoon_task_8h',
        name='Tarea Tarde (18:00, L-V - 8h)',
        replace_existing=True,
        misfire_grace_time=60
    )

    # scheduler.start()  <-- Se elimina de aquí, se inicia en main
    logger.info("✅ Scheduler configurado correctamente")
    logger.info("📅 Tareas programadas (Lunes a Viernes):")
    logger.info("   • 09:00 - Login + Fichaje (ambas jornadas)")
    logger.info("   • 17:00 - Stop (jornada de 7h)")
    logger.info("   • 18:00 - Stop (jornada de 8h)")


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
    app.add_handler(CommandHandler("workday", handle_workday_command))
    app.add_handler(CommandHandler("workday_set", handle_workday_set_command))
    app.add_handler(CommandHandler("vacation", handle_vacation_command))
    app.add_handler(CommandHandler("vacation_list", handle_vacation_list_command))
    app.add_handler(CommandHandler("vacation_delete", handle_vacation_delete_command))

    bot_state["app"] = app

    logger.info("✅ Handlers de Telegram inicializados")
    logger.info("📱 Comandos disponibles:")
    logger.info("   • /start - Reanudar bot")
    logger.info("   • /stop - Pausar bot")
    logger.info("   • /status - Ver estado")
    logger.info("   • /workday - Ver jornada actual")
    logger.info("   • /workday_set - Cambiar jornada")
    logger.info("   • /vacation - Agregar vacaciones")
    logger.info("   • /vacation_list - Ver vacaciones")
    logger.info("   • /vacation_delete - Eliminar vacación")

    return app


async def main() -> None:
    """Función principal - mantiene el bot corriendo 24/7"""
    global event_loop, scheduler, telegram_bot, bot_state
    event_loop = asyncio.get_event_loop()

    logger.info("\n" + "🤖 " * 20)
    logger.info("INICIALIZANDO BOT DE BIXPE - MODO 24/7 CON TELEGRAM")
    logger.info("🤖 " * 20 + "\n")

    if USERNAME == "tu_usuario" or PASSWORD == "tu_contraseña":
        logger.error("❌ CREDENCIALES DE BIXPE NO CONFIGURADAS")
        logger.error("❌ Establece BIXPE_USERNAME y BIXPE_PASSWORD en variables de entorno")
        return

    if not TELEGRAM_TOKEN:
        logger.warning("⚠️ TELEGRAM_TOKEN no configurado - Comandos deshabilitados")
    if not TELEGRAM_CHAT_ID:
        logger.warning("⚠️ TELEGRAM_CHAT_ID no configurado - Notificaciones deshabilitadas")

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
        jornada = load_jornada()
        await send_telegram_notification(f"🤖 <b>Bot iniciado - Modo 24/7 activado</b>\n\n📅 Próximas tareas (Lunes a Viernes):\n• 09:00 - Login + Fichaje\n• {jornada['salida']:02d}:00 - Finalizar jornada de {jornada['horas']}h\n\n📱 Usa: /start /stop /status /workday_set")
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
