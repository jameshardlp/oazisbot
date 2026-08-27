"""Планировщик для автоматической публикации постов."""
import asyncio
import logging
import random

import settings
from config import CHANNEL_ID
from content.deepseek import generate_caption_with_validation
from content.media import get_streamer_media
from bot_modules.client import bot

logger = logging.getLogger(__name__)


async def publish_post():
    """Публикует один пост в канал (только текст, без видео).

    Генерация и поиск клипа синхронные и долгие (до 20 сетевых попыток к
    DeepSeek плюс обход поисковиков), поэтому выполняются в отдельном потоке —
    иначе на это время event loop замирает и бот не отвечает на команды.
    """
    try:
        # Режим проверяем до генерации, а не только перед отправкой: иначе
        # задача, поднятая в зазоре между /mode и остановкой планировщика,
        # молотила DeepSeek минутами и в логах это выглядело как «бот всё ещё
        # постит стримеров, хотя включены мемы».
        if settings.get_content_mode() != "streamers":
            logger.info("ℹ️ Режим не streamers — пост про стримера не генерирую")
            return

        logger.info("📢 Начинаю публикацию поста про стримера...")

        # Отмена задачи не останавливает рабочий поток, поэтому даём генерации
        # собственную причину прекратиться: между попытками она смотрит, не
        # сменился ли режим.
        def mode_left_streamers() -> bool:
            return settings.get_content_mode() != "streamers"

        caption, streamer_key = await asyncio.to_thread(
            generate_caption_with_validation, mode_left_streamers
        )

        if not caption:
            logger.warning("⚠️ Пост не сгенерирован")
            return

        logger.info(f"✅ Пост сгенерирован ({len(caption)} символов)")

        # Поиск клипа — ещё минуты сетевой работы, и делать его в режиме мемов
        # уже незачем
        if mode_left_streamers():
            logger.info("ℹ️ Режим уже не streamers — клип не ищу, пост не публикую")
            return

        # Ищем клип (только ссылку, НЕ пытаемся отправить видео)
        if streamer_key:
            media_url, media_type = await asyncio.to_thread(
                get_streamer_media, streamer_key, streamer_key
            )
            if media_url:
                # Добавляем ссылку на клип в текст поста
                caption = f"{caption}\n\n🔗 {media_url}"
                logger.info(f"🔗 Добавлена ссылка на клип: {media_url[:50]}...")

        # Генерация занимает минуты, за это время режим могли переключить.
        # Задачу в таком случае гасит content_supervisor, но между /mode и
        # отменой есть зазор — попасть в него пост про стримера не должен.
        if settings.get_content_mode() != "streamers":
            logger.info("ℹ️ Режим уже не streamers — готовый пост не публикую")
            return

        # Отправляем ТОЛЬКО ТЕКСТ
        if CHANNEL_ID:
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=caption
            )
            logger.info("✅ Пост опубликован!")
        else:
            logger.warning("⚠️ CHANNEL_ID не задан")

    except asyncio.CancelledError:
        # Поток с генерацией остановить нельзя, но он сам проверяет режим между
        # попытками (mode_left_streamers) и завершится на ближайшей. Текущий
        # запрос к DeepSeek при этом домолотит и попадёт в лог.
        logger.info(
            "🛑 Генерация поста про стримера прервана (обычно сменой режима). "
            "Фоновый поток остановится на следующей попытке, пост опубликован "
            "не будет."
        )
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")

async def scheduler():
    """Цикл планировщика для постов про стримеров."""
    logger.info("=" * 60)
    logger.info("📸 ПЛАНИРОВЩИК СТРИМЕРОВ ЗАПУЩЕН")
    logger.info(f"📡 Канал: {CHANNEL_ID}")
    logger.info(f"⏱️ Интервал: {settings.describe_interval()} (меняется командой /interval)")
    logger.info("=" * 60)

    await asyncio.sleep(random.randint(10, 30))
    await publish_post()

    while True:
        interval = settings.next_interval_seconds()
        logger.info(f"⏳ Следующий пост через {settings.format_interval(interval)}")

        # Не asyncio.sleep: /interval должен подействовать сразу, а не через часы
        if await settings.wait_for_next_post(interval):
            logger.info("♻️ Интервал изменён, отсчёт пошёл заново")
            continue

        await publish_post()
