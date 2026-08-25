# webhook_runner.py
"""Запуск вебхук сервера FreeKassa и AuraPay."""
import asyncio
import logging
import os
import sys

from aiohttp import web
from payments.webhooks import freekassa_webhook, aurapay_webhook

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    """Запускает вебхук сервер."""
    port = int(os.getenv("WEBHOOK_PORT", 8081))
    app = web.Application()
    app.router.add_post("/freekassa/webhook", freekassa_webhook)
    app.router.add_post("/aurapay/webhook", aurapay_webhook)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"🌐 Webhook сервер запущен на порту {port}")
    
    # Держим сервер активным
    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Webhook сервер остановлен")
    except Exception as e:
        logger.error(f"❌ Фатальная ошибка: {e}")
        sys.exit(1)