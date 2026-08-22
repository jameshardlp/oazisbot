"""Точка входа бота: вебхук-сервер + long polling."""
import asyncio
import logging
import os
import sys

from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

from config import FREEKASSA_SHOP_ID, FREEKASSA_SECRET1, SEND_DELAY
from telegram.client import bot, dp
from telegram import handlers
from telegram.scheduler import scheduler
from telegram.meme_scheduler import meme_scheduler
from payments.webhooks import freekassa_webhook, aurapay_webhook

# Импортируем обработчик для /broadcast
from telegram.handlers.broadcast import get_broadcast_conversation_handler, broadcast_callback

# Импортируем обработчик для /resend
from telegram.handlers.resend import get_resend_conversation_handler

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


async def main() -> None:
    logger.info("=" * 60)
    logger.info("🤖 БОТ ЗАПУЩЕН")
    logger.info("📸 Посты про стримеров (текст + ссылки на YouTube)")
    logger.info("🎬 Мемы из каналов (скачивание и отправка)")
    logger.info("📦 Источники мемов: videos_dolboyoba, shitcollection, postleftism, noviop")
    logger.info("📤 Команда /resend — отправка контента в канал от имени бота")
    logger.info("=" * 60)

    if FREEKASSA_SHOP_ID and FREEKASSA_SECRET1:
        await start_webhook_server(web.Application())

    # Добавляем обработчик для /broadcast (реклама)
    broadcast_handler = get_broadcast_conversation_handler()
    dp.add_handler(broadcast_handler)
    dp.add_handler(CallbackQueryHandler(broadcast_callback, pattern="^(pay_with_stars|pay_with_card|cancel_broadcast|cancel_stars_payment)$"))

    # Добавляем обработчик для /resend (ручная отправка в канал)
    resend_handler = get_resend_conversation_handler()
    dp.add_handler(resend_handler)

    # Запускаем планировщик стримеров
    asyncio.create_task(scheduler())
    
    # Запускаем планировщик мемов
    asyncio.create_task(meme_scheduler())

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "pre_checkout_query"])


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен")
    except Exception as e:
        logger.error(f"❌ Фатальная ошибка: {e}")
        sys.exit(1)
