"""Точка входа бота: вебхук-сервер + long polling."""
import asyncio
import logging
import os
import sys

from aiohttp import web

# Импорты из установленной библиотеки python-telegram-bot
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, CommandHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

from config import FREEKASSA_SHOP_ID, FREEKASSA_SECRET1, SEND_DELAY, BOT_TOKEN
from bot_modules.client import application
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


def start_bot() -> None:
    """Запускает бота через Application для версии 20.7."""
    logger.info("=" * 60)
    logger.info("🤖 БОТ ЗАПУЩЕН (версия 20.7)")
    logger.info("📸 Посты про стримеров (текст + ссылки на YouTube)")
    logger.info("🎬 Мемы из каналов (скачивание и отправка)")
    logger.info("📦 Источники мемов: videos_dolboyoba, shitcollection, postleftism, noviop")
    logger.info("📤 Команда /resend — отправка контента в канал от имени бота")
    logger.info("=" * 60)

    # Создаём Application для версии 20.7
    app = Application.builder().token(BOT_TOKEN).build()

    # Регистрируем административные команды
    register_admin_handlers(app)

    # Добавляем обработчик для /broadcast (реклама)
    broadcast_handler = get_broadcast_conversation_handler()
    app.add_handler(broadcast_handler)
    app.add_handler(CallbackQueryHandler(broadcast_callback, pattern="^(pay_with_stars|pay_with_card|cancel_broadcast|cancel_stars_payment)$"))

    # Добавляем обработчик для /resend (ручная отправка в канал)
    resend_handler = get_resend_conversation_handler()
    app.add_handler(resend_handler)

    # Запускаем планировщик стримеров
    asyncio.create_task(scheduler())
    
    # Запускаем планировщик мемов
    asyncio.create_task(meme_scheduler())

    # Запускаем polling через Application
    app.run_polling()


async def main() -> None:
    """Основная асинхронная функция."""
    if FREEKASSA_SHOP_ID and FREEKASSA_SECRET1:
        await start_webhook_server(web.Application())
    
    # Запускаем бота синхронно в отдельном потоке
    import threading
    bot_thread = threading.Thread(target=start_bot)
    bot_thread.start()
    
    # Ждём завершения
    bot_thread.join()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен")
    except Exception as e:
        logger.error(f"❌ Фатальная ошибка: {e}")
        sys.exit(1)
