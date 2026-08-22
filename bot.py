"""Точка входа бота: вебхук-сервер + long polling."""
import asyncio
import logging
import os
import sys
import signal

from aiohttp import web

# Импорты из установленной библиотеки python-telegram-bot
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, CommandHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

from config import FREEKASSA_SHOP_ID, FREEKASSA_SECRET1, SEND_DELAY, BOT_TOKEN
from bot_modules.client import application, bot
from bot_modules import handlers
from bot_modules.scheduler import scheduler
from bot_modules.meme_scheduler import meme_scheduler
from payments.webhooks import freekassa_webhook, aurapay_webhook

# Импортируем обработчик для /broadcast
from bot_modules.handlers.broadcast import get_broadcast_conversation_handler, broadcast_callback

# Импортируем обработчик для /resend
from bot_modules.handlers.resend import get_resend_conversation_handler

# Импортируем административные обработчики
from bot_modules.handlers.admin import register_admin_handlers

logger = logging.getLogger(__name__)


async def start_webhook_server(app: web.Application) -> None:
    """Поднимает сервер для приёма вебхуков FreeKassa и AuraPay."""
    port = int(os.getenv("PORT", 8080))
    app.router.add_post("/freekassa/webhook", freekassa_webhook)
    app.router.add_post("/aurapay/webhook", aurapay_webhook)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"🌐 Webhook сервер на порту {port}")


async def shutdown_tasks() -> None:
    """Корректно завершает задачи."""
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


async def main() -> None:
    """Основная асинхронная функция."""
    logger.info("=" * 60)
    logger.info("🤖 БОТ ЗАПУЩЕН")
    logger.info("📸 Посты про стримеров (текст + ссылки на YouTube)")
    logger.info("🎬 Мемы из каналов (скачивание и отправка)")
    logger.info("📦 Источники мемов: videos_dolboyoba, shitcollection, postleftism, noviop")
    logger.info("📤 Команда /resend — отправка контента в канал от имени бота")
    logger.info("=" * 60)

    # Запускаем webhook сервер
    web_app = web.Application()
    if FREEKASSA_SHOP_ID and FREEKASSA_SECRET1:
        await start_webhook_server(web_app)

    # Регистрируем административные команды
    register_admin_handlers(application)

    # Добавляем обработчик для /broadcast (реклама)
    broadcast_handler = get_broadcast_conversation_handler()
    application.add_handler(broadcast_handler)
    application.add_handler(CallbackQueryHandler(broadcast_callback, pattern="^(pay_with_stars|pay_with_card|cancel_broadcast|cancel_stars_payment)$"))

    # Добавляем обработчик для /resend (ручная отправка в канал)
    resend_handler = get_resend_conversation_handler()
    application.add_handler(resend_handler)

    # Запускаем планировщик стримеров как фоновую задачу
    scheduler_task = asyncio.create_task(scheduler())
    
    # Запускаем планировщик мемов как фоновую задачу
    meme_scheduler_task = asyncio.create_task(meme_scheduler())

    try:
        # Запускаем бота
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        logger.info("✅ Бот запущен и готов к работе")
        
        # Ждём сигнала остановки
        await asyncio.Event().wait()
        
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("🛑 Получен сигнал остановки")
    finally:
        # Корректно завершаем задачи
        logger.info("🔄 Завершаем работу...")
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
        
        # Отменяем фоновые задачи
        scheduler_task.cancel()
        meme_scheduler_task.cancel()
        
        await shutdown_tasks()
        logger.info("✅ Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Фатальная ошибка: {e}")
        sys.exit(1)
