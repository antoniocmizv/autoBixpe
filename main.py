import asyncio
import os
from datetime import datetime
from playwright.async_api import async_playwright
from telegram import Bot
import logging

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

# Instancia del bot de Telegram
telegram_bot = Bot(token=TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None

async def take_screenshot_and_send(page, event_name):
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

async def morning_task():
    """Tarea de las 9:00 - Login y click en botón"""
    async with async_playwright() as p:
        try:
            logger.info("=" * 50)
            logger.info("🌅 INICIANDO TAREA DE MAÑANA (9:00)")
            logger.info("=" * 50)
            
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
            
        except Exception as e:
            logger.error(f"❌ Error en tarea de mañana: {e}", exc_info=True)

async def afternoon_task():
    """Tarea de las 18:00 - Login y click en botón de stop"""
    async with async_playwright() as p:
        try:
            logger.info("=" * 50)
            logger.info("🌆 INICIANDO TAREA DE TARDE (18:00)")
            logger.info("=" * 50)
            
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
                except:
                    logger.warning("⚠️ Popup no encontrado, continuando...")
                
                await take_screenshot_and_send(page, "⏹️ Botón STOP y confirmación completados (18:00)")
            else:
                logger.warning("⚠️ Botón STOP no encontrado")
            
            await browser.close()
            logger.info("🏁 TAREA DE TARDE COMPLETADA\n")
            
        except Exception as e:
            logger.error(f"❌ Error en tarea de tarde: {e}", exc_info=True)

def get_closest_task():
    """Determina qué tarea ejecutar según la hora actual"""
    now = datetime.now()
    current_hour = now.hour
    current_minute = now.minute
    current_time_minutes = current_hour * 60 + current_minute
    
    # Tiempos en minutos desde medianoche
    morning_time = 9 * 60  # 9:00
    afternoon_time = 18 * 60  # 18:00
    
    # Calcular distancias
    distance_to_morning = abs(current_time_minutes - morning_time)
    distance_to_afternoon = abs(current_time_minutes - afternoon_time)
    
    logger.info(f"⏰ Hora actual: {now.strftime('%H:%M:%S')}")
    logger.info(f"📏 Distancia a las 9:00: {distance_to_morning} minutos")
    logger.info(f"📏 Distancia a las 18:00: {distance_to_afternoon} minutos")
    
    if distance_to_morning < distance_to_afternoon:
        logger.info("✨ Más próximo a las 9:00 → Ejecutando TAREA DE MAÑANA")
        return "morning"
    else:
        logger.info("✨ Más próximo a las 18:00 → Ejecutando TAREA DE TARDE")
        return "afternoon"

async def main():
    """Función principal - ejecuta la tarea más cercana"""
    logger.info("\n" + "🤖 " * 20)
    logger.info("INICIALIZANDO BOT DE BIXPE")
    logger.info("🤖 " * 20 + "\n")
    
    logger.info(f"📌 Usuario: {USERNAME}")
    logger.info(f"🔗 URL: {LOGIN_URL}")
    logger.info(f"👁️ Headless: {HEADLESS}\n")
    
    task_type = get_closest_task()
    
    try:
        if task_type == "morning":
            await morning_task()
        else:
            await afternoon_task()
    except KeyboardInterrupt:
        logger.info("\n🛑 Ejecución cancelada por el usuario")
    except Exception as e:
        logger.error(f"\n❌ Error fatal: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
