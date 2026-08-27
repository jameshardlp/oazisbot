"""Точка входа бота: вебхук-сервер + long polling."""
import asyncio
import logging
import os
import sys

from aiohttp import web

# Импорты из установленной библиотеки python-telegram-bot
from telegram.ext import CallbackQueryHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

from config import FREEKASSA_SHOP_ID, FREEKASSA_SECRET1
import settings
from bot_modules.client import application
from bot_modules.scheduler import scheduler
from bot_modules.meme_scheduler import meme_scheduler
from payments.webhooks import freekassa_webhook, aurapay_webhook

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

# Пауза перед подъёмом планировщика, который упал сам: без неё повторяющаяся
# ошибка на старте цикла крутилась бы в лог без остановки
RESTART_DELAY = 10


async def start_webhook_server(app: web.Application) -> None:
    """Поднимает сервер для приёма вебхуков FreeKassa и AuraPay на отдельном порту."""
    # Используем отдельный порт для вебхуков, чтобы не конфликтовать с основным процессом
    port = int(os.getenv("WEBHOOK_PORT", 8081))
    app.router.add_post("/freekassa/webhook", freekassa_webhook)
    app.router.add_post("/aurapay/webhook", aurapay_webhook)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"🌐 Webhook сервер запущен на порту {port}")


async def shutdown_tasks() -> None:
    """Корректно завершает задачи."""
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


async def content_supervisor() -> None:
    """Держит запущенным ровно один планировщик — тот, что задан режимом.

    Планировщик — бесконечный цикл, сам он режим не перечитывает. Поэтому смену
    режима командой /mode обслуживает эта задача: гасит текущий цикл и поднимает
    другой. Без неё /mode подействовала бы только после перезапуска процесса.

    Заодно следит, что планировщик жив: упавшая задача раньше умирала молча
    (её traceback не попадал никуда, а надзор сидел в ожидании смены режима), и
    автопостинг просто прекращался до перезапуска бота.
    """
    task = None
    current_mode = None

    try:
        while True:
            mode = settings.get_content_mode()

            if task is None or mode != current_mode:
                if task is not None:
                    task.cancel()
                    # Ждём фактического завершения: иначе старый планировщик
                    # успел бы опубликовать пост уже после смены режима
                    await asyncio.gather(task, return_exceptions=True)
                    logger.info(f"🛑 Планировщик режима {current_mode} остановлен")

                task = asyncio.create_task(
                    scheduler() if mode == "streamers" else meme_scheduler()
                )
                current_mode = mode

            # clear() до ожидания: если /mode сработала пока мы гасили и поднимали
            # задачи, событие уже взведено и следующий круг начнётся сразу
            settings.mode_changed.clear()
            if settings.get_content_mode() != current_mode:
                continue

            # Ждём того, что случится раньше: смены режима или падения
            # планировщика
            waiter = asyncio.create_task(settings.mode_changed.wait())
            try:
                done, _ = await asyncio.wait(
                    {waiter, task}, return_when=asyncio.FIRST_COMPLETED
                )
            finally:
                waiter.cancel()

            if task in done:
                # Планировщик — бесконечный цикл, сам он завершиться не должен
                if task.cancelled():
                    # Отменили не мы — значит процесс уже останавливается
                    logger.info(f"🛑 Планировщик режима {current_mode} отменён извне")
                    raise asyncio.CancelledError

                exc = task.exception()
                if exc is not None:
                    logger.error(
                        f"❌ Планировщик режима {current_mode} упал: {exc!r}",
                        exc_info=exc,
                    )
                else:
                    logger.error(f"❌ Планировщик режима {current_mode} завершился сам")

                task = None
                logger.info(f"♻️ Перезапуск планировщика через {RESTART_DELAY} с")
                await asyncio.sleep(RESTART_DELAY)
                continue

            logger.info("♻️ Режим контента изменён, меняю планировщик")

    except asyncio.CancelledError:
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        raise


async def main() -> None:
    """Основная асинхронная функция."""
    logger.info("=" * 60)
    logger.info("🤖 БОТ ЗАПУЩЕН")
    if settings.get_content_mode() == "streamers":
        logger.info("📸 Режим контента: СТРИМЕРЫ (текст + ссылки на YouTube)")
    else:
        logger.info("🎬 Режим контента: МЕМЫ из каналов (скачивание и отправка)")
        channels = settings.get_meme_channels()
        logger.info(
            f"📦 Источники мемов: {', '.join(channels) if channels else 'не заданы — /sources add'}"
        )
    logger.info(f"⏱️ Интервал между постами: {settings.describe_interval()}")
    logger.info(f"💾 Настройки: {settings.describe_storage()}")
    if not settings.loaded_from_file():
        # Самая частая жалоба «бот снова постит стримеров, хотя включены мемы»:
        # файл настроек пропал вместе с контейнером, и /mode откатился к
        # значению из окружения.
        logger.warning(
            "⚠️ Файл настроек не найден — режим, интервал и список каналов взяты "
            "по умолчанию. Если /mode переключали раньше, значит диск хостинга "
            "эфемерный: задай нужный режим переменной CONTENT_MODE или укажи "
            "SETTINGS_FILE на постоянном томе."
        )
    logger.info("📤 Команда /resend — отправка контента в канал от имени бота")
    logger.info("📸 Команда /photo — случайное фото стримера")
    logger.info("🔀 Команда /mode — режим контента: стримеры или мемы")
    logger.info("⏱️ Команда /interval — интервал между автопостами")
    logger.info("🚀 Команда /postnow — выложить мем из каналов прямо сейчас")
    logger.info("📦 Команда /sources — список каналов, откуда берутся мемы")
    logger.info("🌐 Webhook сервер FreeKassa на порту 8081")
    logger.info("=" * 60)

    # Удаляем вебхук перед запуском (чтобы избежать конфликтов)
    try:
        await application.bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Вебхук удалён")
        await asyncio.sleep(2)
    except Exception as e:
        logger.warning(f"⚠️ Ошибка удаления вебхука: {e}")

    # Запускаем webhook сервер FreeKassa/AuraPay на отдельном порту
    web_app = web.Application()
    if FREEKASSA_SHOP_ID and FREEKASSA_SECRET1:
        await start_webhook_server(web_app)
    else:
        logger.info("ℹ️ FreeKassa не настроен, webhook сервер не запущен")

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

    # Планировщик контента поднимает надзорная задача: режим меняется командой
    # /mode, и тогда один цикл нужно погасить, а другой запустить
    content_task = asyncio.create_task(content_supervisor())

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
        await asyncio.gather(content_task, return_exceptions=True)
        
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