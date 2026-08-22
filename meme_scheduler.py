# telegram/meme_scheduler.py
"""Планировщик для публикации мемов (дополнительный функционал)."""
import asyncio
import logging
import random
from datetime import datetime, timedelta

from config import CHANNEL_ID
from content.meme_parser import get_random_meme
from telegram.client import bot

logger = logging.getLogger(__name__)

# Интервал публикации мемов (1-3 часа)
MIN_INTERVAL = 3600  # 1 час
MAX_INTERVAL = 10800  # 3 часа

async def send_meme_to_channel() -> bool:
    """Отправляет один мем в канал."""
    try:
        meme = get_random_meme()
        if not meme:
            logger.warning("⚠️ Нет доступных мемов")
            return False
        
        media_url = meme.get('media_url')
        media_type = meme.get('media_type')
        
        if not media_url:
            return False
        
        logger.info(f"📤 Отправляю мем (тип: {media_type})")
        
        if media_type == 'photo':
            await bot.send_photo(chat_id=CHANNEL_ID, photo=media_url)
        elif media_type == 'video':
            await bot.send_video(chat_id=CHANNEL_ID, video=media_url)
        elif media_type == 'animation':
            await bot.send_animation(chat_id=CHANNEL_ID, animation=media_url)
        else:
            await bot.send_document(chat_id=CHANNEL_ID, document=media_url)
        
        logger.info("✅ Мем опубликован!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка публикации мема: {e}")
        return False

async def meme_scheduler():
    """Цикл планировщика мемов."""
    logger.info("=" * 60)
    logger.info("🎬 ПЛАНИРОВЩИК МЕМОВ ЗАПУЩЕН")
    logger.info(f"📡 Канал: {CHANNEL_ID}")
    logger.info(f"⏱️ Интервал: 1-3 часа")
    logger.info("📦 Источники: videos_dolboyoba, shitcollection, postleftism, noviop")
    logger.info("=" * 60)
    
    # Первый мем через 30-60 секунд
    await asyncio.sleep(random.randint(30, 60))
    await send_meme_to_channel()
    
    while True:
        interval = random.randint(MIN_INTERVAL, MAX_INTERVAL)
        logger.info(f"⏳ Следующий мем через {interval // 3600}ч {(interval % 3600) // 60}м")
        await asyncio.sleep(interval)
        await send_meme_to_channel()