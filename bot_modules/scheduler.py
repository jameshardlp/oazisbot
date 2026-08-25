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
        logger.info("📢 Начинаю публикацию поста про стримера...")

        # Генерируем пост
        caption, streamer_key = await asyncio.to_thread(generate_caption_with_validation)

        if not caption:
            logger.warning("⚠️ Пост не сгенерирован")
            return

        logger.info(f"✅ Пост сгенерирован ({len(caption)} символов)")

        # Ищем клип (только ссылку, НЕ пытаемся отправить видео)
        if streamer_key:
            media_url, media_type = await asyncio.to_thread(
                get_streamer_media, streamer_key, streamer_key
            )
            if media_url:
                # Добавляем ссылку на клип в текст поста
                caption = f"{caption}\n\n🔗 {media_url}"
                logger.info(f"🔗 Добавлена ссылка на клип: {media_url[:50]}...")
        
        # Отправляем ТОЛЬКО ТЕКСТ
        if CHANNEL_ID:
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=caption
            )
            logger.info("✅ Пост опубликован!")
        else:
            logger.warning("⚠️ CHANNEL_ID не задан")
            
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
