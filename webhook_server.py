# webhook_server.py
"""Отдельный сервер для вебхуков FreeKassa и AuraPay."""
import os
from aiohttp import web
from payments.webhooks import freekassa_webhook, aurapay_webhook


async def start_webhook_server():
    """Запускает вебхук сервер на отдельном порту."""
    port = int(os.getenv("WEBHOOK_PORT", 8081))  # Отдельный порт для вебхуков
    app = web.Application()
    app.router.add_post("/freekassa/webhook", freekassa_webhook)
    app.router.add_post("/aurapay/webhook", aurapay_webhook)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 Webhook сервер запущен на порту {port}")
    
    # Держим сервер активным
    while True:
        await asyncio.sleep(1)