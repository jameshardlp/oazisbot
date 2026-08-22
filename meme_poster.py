# telegram/meme_poster.py
"""Публикация мемов в канал."""
import logging
import asyncio
import random
from datetime import datetime, timedelta

from config import CHANNEL_ID
from content.meme_parser import get_random_meme
from telegram.client import bot

logger = logging.getLogger(__name__)

# Настройки публикации мемов
MIN_INTERVAL_HOURS = 1  # Не чаще 1 раза в час
MAX_INTERVAL_HOURS = 3  # Не реже 1 раза в 3 часа

MIN_INTERVAL = MIN_INTERVAL_HOURS * 3600
MAX_INTERVAL = MAX_INTERVAL_HOURS * 3600

async def send_meme_to_channel() -> bool:
    """Отправляет один мем в канал."""
    try:
        # Получаем случайный мем
        meme = get_random_meme()
        if not meme:
            logger.warning("⚠️ Нет доступных мемов для публикации")
            return False
        
        media_url = meme.get('media_url')
        media_type = meme.get('media_type')
        post_id = meme.get('post_id', 'unknown')
        
        if not media_url:
            logger.warning("⚠️ Мем без URL, пропускаю")
            return False
        
        logger.info(f"📤 Отправляю мем (ID: {post_id}, тип: {media_type})")
        
        # Отправляем в зависимости от типа
        if media_type == 'photo':
            await bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=media_url
            )
        elif media_type == 'video':
            await bot.send_video(
                chat_id=CHANNEL_ID,
                video=media_url
            )
        elif media_type == 'animation':
            await bot.send_animation(
                chat_id=CHANNEL_ID,
                animation=media_url
            )
        else:
            # Пробуем отправить как документ
            await bot.send_document(
                chat_id=CHANNEL_ID,
                document=media_url
            )
        
        logger.info(f"✅ Мем (ID: {post_id}) опубликован в канал!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка публикации мема: {e}")
        return False

async def meme_scheduler():
    """Цикл планировщика для публикации мемов."""
    logger.info("=" * 60)
    logger.info("🎬 ПЛАНИРОВЩИК МЕМОВ ЗАПУЩЕН")
    logger.info(f"📡 Канал: {CHANNEL_ID}")
    logger.info(f"⏱️ Интервал: от {MIN_INTERVAL_HOURS} до {MAX_INTERVAL_HOURS} часов")
    logger.info("📦 Источники: videos_dolboyoba, shitcollection, postleftism, noviop")
    logger.info("=" * 60)
    
    # Первый мем через 10-30 секунд
    first_delay = random.randint(10, 30)
    logger.info(f"⏳ Первый мем через {first_delay} секунд...")
    await asyncio.sleep(first_delay)
    await send_meme_to_channel()
    
    count = 1
    
    while True:
        next_interval = random.randint(MIN_INTERVAL, MAX_INTERVAL)
        hours = next_interval // 3600
        minutes = (next_interval % 3600) // 60
        
        logger.info(f"⏳ Следующий мем через {hours}ч {minutes}м")
        logger.info(f"📅 Ожидаемое время: {(datetime.now() + timedelta(seconds=next_interval)).strftime('%H:%M:%S')}")
        
        await asyncio.sleep(next_interval)
        
        success = await send_meme_to_channel()
        if success:
            count += 1
            logger.info(f"📊 Всего опубликовано мемов: {count}")
        else:
            logger.warning("⚠️ Публикация мема не удалась, пробую дальше...")