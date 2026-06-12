import asyncio
import logging
import os
import sys
import time
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web
import aiohttp

import config
from database import db
from handlers import get_handlers_router

# Loglarni sozlash
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Web Server (Free Hosting uchun port ochish va faollikni ta'minlash)
async def handle_ping(request):
    return web.Response(text="Bot faol va 24/7 ishlamoqda!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    app.router.add_get('/ping', handle_ping)
    
    port = int(os.getenv("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    try:
        await site.start()
        logger.info(f"Ping veb-serveri {port}-portda ishga tushirildi.")
    except Exception as e:
        logger.warning(f"Veb-serverni {port}-portda ishga tushirib bo'lmadi: {e}")

# Self-Ping (Hosting uyquga ketmasligi uchun o'ziga so'rov yuborib turadi)
async def self_ping_loop():
    app_url = os.getenv("APP_URL") or os.getenv("RENDER_EXTERNAL_URL")
    if not app_url:
        logger.info("Self-ping faollashtirilmadi (APP_URL yoki RENDER_EXTERNAL_URL topilmadi).")
        return
        
    logger.info(f"Self-ping faollashtirildi: {app_url}")
    await asyncio.sleep(30)  # Ishga tushgandan keyin biroz kutish
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(app_url) as response:
                    logger.info(f"Self-ping muvaffaqiyatli yuborildi. Status: {response.status}")
            except Exception as e:
                logger.warning(f"Self-ping yuborishda xatolik: {e}")
            await asyncio.sleep(240)  # Har 4 daqiqada o'ziga so'rov yuborish

# Uyqu holatini aniqlash (Sleep detector)
async def sleep_detector_loop(bot: Bot):
    ping_file = "last_ping.txt"
    await asyncio.sleep(20)  # Bot to'liq ishlab ketishi uchun kutish
    
    if os.path.exists(ping_file):
        try:
            with open(ping_file, "r") as f:
                last_ping = float(f.read().strip())
            current = time.time()
            # Agar bot 10 daqiqadan ko'p vaqt davomida to'xtab qolgan bo'lsa (uyqu holati)
            if current - last_ping > 600:
                offline_mins = int((current - last_ping) / 60)
                logger.warning(f"Uyqu holati aniqlandi: Bot {offline_mins} daqiqa ishlamagan.")
                for admin_id in config.ADMIN_IDS:
                    try:
                        await bot.send_message(
                            chat_id=admin_id,
                            text=f"⚠️ Bot taxminan {offline_mins} daqiqa davomida uyqu rejimiga kirdi (sleep mode yoki crash yuz berdi).\n\n"
                                 f"Foydalanuvchilarga 24/7 uzluksiz xizmat ko'rsatish uchun botni boshqa "
                                 f"bepul hostingga (masalan, Railway yoki Koyeb) o'tkazishni maslahat beramiz."
                        )
                    except Exception as e:
                        logger.error(f"Adminga ogohlantirish yuborishda xatolik (ID: {admin_id}): {e}")
        except Exception as e:
            logger.error(f"Ping faylini o'qishda xatolik: {e}")

    # Har 1 daqiqada vaqtni yangilab boramiz
    while True:
        try:
            with open(ping_file, "w") as f:
                f.write(str(time.time()))
        except Exception as e:
            logger.error(f"Ping fayliga yozishda xatolik: {e}")
        await asyncio.sleep(60)

async def main():
    if not config.BOT_TOKEN:
        logger.critical("BOT_TOKEN topilmadi! Iltimos, atrof-muhit o'zgaruvchilarini tekshiring.")
        sys.exit(1)
        
    # Bazaga ulanish
    try:
        await db.connect()
        # Env faylidagi adminlarni bazaga asosiy admin qilib yozib qo'yamiz (seed)
        await db.seed_main_admins(config.ADMIN_IDS)
    except Exception as e:
        logger.critical(f"Ma'lumotlar bazasiga ulanishda xatolik: {e}")
        sys.exit(1)
        
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    
    # Routerlarni ulash
    dp.include_router(get_handlers_router())
    
    # Background vazifalarni boshlash
    asyncio.create_task(start_web_server())
    asyncio.create_task(self_ping_loop())
    asyncio.create_task(sleep_detector_loop(bot))
    
    logger.info("Bot ishga tushishga tayyor.")
    
    # Avtomatik qayta ulanish va restart himoyasi tizimi
    while True:
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info("Polling ishga tushirilmoqda...")
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        except Exception as e:
            logger.error(f"Polling davomida kutilmagan xatolik yuz berdi: {e}")
            logger.info("Bot 5 soniyadan so'ng avtomatik qayta ulanadi...")
            await asyncio.sleep(5)
        finally:
            try:
                await bot.session.close()
            except Exception:
                pass
            # Qayta ulanish uchun yangi bot obyektini yaratamiz
            bot = Bot(token=config.BOT_TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot o'chirildi.")
