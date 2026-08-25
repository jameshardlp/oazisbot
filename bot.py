"""Точка входа бота: вебхук-сервер + long polling."""
import asyncio
import logging
import sys

# Импорты из установленной библиотеки python-telegram-bot
from telegram.ext import CallbackQueryHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

from config import CONTENT_MODE
import settings
from bot_modules.client import application
from bot_modules.scheduler import scheduler
from bot_modules.meme_scheduler import meme_scheduler

# Импортируем обработчик для /broadcast
from bot_modules.handlers.broadcast import get_broadcast_conversation_handler, broadcast_callback

# Импортируем обработчик для /resend
from bot_modules.handlers.resend import get_resend_conversation_handler

# Импортируем административные обработчики
from bot_modules.handlers.admin import register_admin_handlers

# Импортируем базовые обработчики
from bot_modules.handlers.basic import register_basic_handlers

# Импортируем обработчик для /photo
from bot_modules.handlers.photo import register_photo_handler

# Импортируем команды управления контентом (/interval, /postnow, /sources)
from bot_modules.handlers.content_admin import register_content_admin_handlers

logger = logging.getLogger(__name__)


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
    if CONTENT_MODE == "streamers":
        logger.info("📸 Режим контента: СТРИМЕРЫ (текст + ссылки на YouTube)")
    else:
        logger.info("🎬 Режим контента: МЕМЫ из каналов (скачивание и отправка)")
        channels = settings.get_meme_channels()
        logger.info(
            f"📦 Источники мемов: {', '.join(channels) if channels else 'не заданы — /sources add'}"
        )
    logger.info(f"⏱️ Интервал между постами: {settings.describe_interval()}")
    logger.info("📤 Команда /resend — отправка контента в канал от имени бота")
    logger.info("📸 Команда /photo — случайное фото стримера")
    logger.info("⏱️ Команда /interval — интервал между автопостами")
    logger.info("🚀 Команда /postnow — выложить мем из каналов прямо сейчас")
    logger.info("📦 Команда /sources — список каналов, откуда берутся мемы")
    logger.info("🌐 Вебхук сервер FreeKassa запускается отдельно (webhook_server.py)")
    logger.info("=" * 60)

    # Удаляем вебхук перед запуском (чтобы избежать конфликтов)
    try:
        await application.bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Вебхук удалён")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка удаления вебхука: {e}")

    # Регистрируем ВСЕ обработчики команд
    register_admin_handlers(application)
    register_basic_handlers(application)
    register_photo_handler(application)
    register_content_admin_handlers(application)

    # Добавляем обработчик для /broadcast (реклама)
    broadcast_handler = get_broadcast_conversation_handler()
    application.add_handler(broadcast_handler)
    application.add_handler(CallbackQueryHandler(broadcast_callback, pattern="^(pay_with_stars|pay_with_card|cancel_broadcast|cancel_stars_payment)$"))

    # Добавляем обработчик для /resend (ручная отправка в канал)
    resend_handler = get_resend_conversation_handler()
    application.add_handler(resend_handler)

    # Запускаем ровно один планировщик контента — тот, что выбран в CONTENT_MODE
    if CONTENT_MODE == "streamers":
        content_task = asyncio.create_task(scheduler())
    else:
        content_task = asyncio.create_task(meme_scheduler())

    try:
        # Запускаем бота
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        logger.info("✅ Бот запущен и готов к работе")
        
        # Держим бота активным
        while True:
            await asyncio.sleep(1)
        
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("🛑 Получен сигнал остановки")
    finally:
        # Корректно завершаем задачи
        logger.info("🔄 Завершаем работу...")
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
        
        # Отменяем фоновую задачу планировщика
        content_task.cancel()
        
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