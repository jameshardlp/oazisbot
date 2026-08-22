"""Планировщик для автоматической публикации постов."""
import asyncio
import logging
import random
from datetime import datetime, timedelta

from config import CHANNEL_ID
from content.deepseek import generate_caption_with_validation
from content.media import get_streamer_media
from bot_modules.client import bot

logger = logging.getLogger(__name__)

MIN_INTERVAL_HOURS = 1
MAX_INTERVAL_HOURS = 3
MIN_INTERVAL = MIN_INTERVAL_HOURS * 3600
MAX_INTERVAL = MAX_INTERVAL_HOURS * 3600
MIN_POSTS_PER_DAY = 24 // MAX_INTERVAL_HOURS

async def publish_post():
    """Публикует один пост в канал (только текст, без видео)."""
    try:
        logger.info("📢 Начинаю публикацию поста про стримера...")
        
        # Генерируем пост
        caption, streamer_key = generate_caption_with_validation()
        
        if not caption:
            logger.warning("⚠️ Пост не сгенерирован")
            return
        
        logger.info(f"✅ Пост сгенерирован ({len(caption)} символов)")
        
        # Ищем клип (только ссылку, НЕ пытаемся отправить видео)
        if streamer_key:
            media_url, media_type = get_streamer_media(streamer_key, streamer_key)
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
    logger.info(f"⏱️ Интервал: {MIN_INTERVAL_HOURS}-{MAX_INTERVAL_HOURS} часа")
    logger.info("=" * 60)
    
    await asyncio.sleep(random.randint(10, 30))
    await publish_post()
    
    while True:
        interval = random.randint(MIN_INTERVAL, MAX_INTERVAL)
        hours = interval // 3600
        minutes = (interval % 3600) // 60
        
        logger.info(f"⏳ Следующий пост через {hours}ч {minutes}м")
        await asyncio.sleep(interval)
        await publish_post()
