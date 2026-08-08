"""Точка входа бота: вебхук-сервер + long polling."""
import asyncio
import logging
import os
import sys

from aiohttp import web

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# ===== АБСОЛЮТНЫЕ ИМПОРТЫ =====
from config import FREEKASSA_SHOP_ID, FREEKASSA_SECRET1, SEND_DELAY
from telegram.client import bot, dp
from telegram import handlers
from telegram.scheduler import scheduler
from payments.webhooks import freekassa_webhook, aurapay_webhook

logger = logging.getLogger(__name__)


async def start_webhook_server(app: web.Application) -> None:
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
    logger.info("📸 85% постов про стримеров, 15% про Азию")
    logger.info(f"⏱️ Задержка между сообщениями: {SEND_DELAY} секунд")
    logger.info("=" * 60)

    if FREEKASSA_SHOP_ID and FREEKASSA_SECRET1:
        await start_webhook_server(web.Application())

    asyncio.create_task(scheduler())

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
