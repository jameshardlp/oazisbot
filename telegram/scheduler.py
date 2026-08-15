"""Планировщик для автоматической публикации постов."""
import asyncio
import logging
import random
from datetime import datetime, timedelta

from config import CHANNEL_ID
from content.deepseek import generate_caption_with_validation
from content.media import get_streamer_media, get_asia_photo
from telegram.client import bot

logger = logging.getLogger(__name__)

# ===== НАСТРОЙКИ ИНТЕРВАЛА =====
MIN_INTERVAL_HOURS = 1
MAX_INTERVAL_HOURS = 3

MIN_INTERVAL = MIN_INTERVAL_HOURS * 3600
MAX_INTERVAL = MAX_INTERVAL_HOURS * 3600
MIN_POSTS_PER_DAY = 24 // MAX_INTERVAL_HOURS

logger.info(f"⏰ Настройки планировщика:")
logger.info(f"   📊 Минимум постов в день: {MIN_POSTS_PER_DAY}")
logger.info(f"   ⏱️ Интервал: от {MIN_INTERVAL_HOURS} до {MAX_INTERVAL_HOURS} часов")

async def publish_post():
    """Публикует один пост в канал."""
    try:
        logger.info("📢 Начинаю публикацию автоматического поста...")
        
        # Генерируем пост
        caption, streamer_key = generate_caption_with_validation()
        
        if not caption:
            logger.warning("⚠️ Пост не сгенерирован, пропускаю публикацию")
            return
        
        logger.info(f"✅ Пост сгенерирован (длина: {len(caption)} символов)")
        logger.info(f"📝 Текст: {caption[:100]}...")
        
        # ===== ПОИСК МЕДИА =====
        media_url = None
        media_type = None
        
        if streamer_key:
            # Тема: стример
            logger.info(f"🔍 Ищу медиа для стримера: {streamer_key}")
            media_url, media_type = get_streamer_media(streamer_key, streamer_key)
            if media_url:
                logger.info(f"✅ Найдено медиа: {media_type}")
            else:
                logger.warning("⚠️ Медиа для стримера не найдено! Будет только текст.")
        else:
            # Тема: Азия
            logger.info("🔍 Ищу азиатское фото...")
            media_url = get_asia_photo()
            if media_url:
                media_type = 'photo'
                logger.info("✅ Найдено азиатское фото")
            else:
                logger.warning("⚠️ Азиатское фото не найдено! Будет только текст.")
        
        # ===== ПУБЛИКАЦИЯ =====
        if not CHANNEL_ID:
            logger.warning("⚠️ CHANNEL_ID не задан, пост не отправлен")
            return
        
        if media_url and media_type == 'clip':
            await bot.send_video(
                chat_id=CHANNEL_ID,
                video=media_url,
                caption=caption
            )
            logger.info(f"✅ Пост с видео опубликован в канал!")
        elif media_url and media_type == 'photo':
            await bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=media_url,
                caption=caption
            )
            logger.info(f"✅ Пост с фото опубликован в канал!")
        else:
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=caption
            )
            logger.info(f"✅ Текстовый пост опубликован в канал!")
            
    except Exception as e:
        logger.error(f"❌ Ошибка публикации поста: {e}")

async def scheduler():
    """Основной цикл планировщика с интервалом 1-3 часа."""
    logger.info("=" * 60)
    logger.info("⏰ ПЛАНИРОВЩИК ЗАПУЩЕН")
    logger.info(f"📊 Минимум постов в день: {MIN_POSTS_PER_DAY}")
    logger.info(f"⏱️ Интервал между постами: от {MIN_INTERVAL_HOURS} до {MAX_INTERVAL_HOURS} часов")
    logger.info(f"📡 Канал для публикации: {CHANNEL_ID}")
    logger.info("=" * 60)
    
    # Первый пост через 10-30 секунд
    first_delay = random.randint(10, 30)
    logger.info(f"⏳ Первый пост через {first_delay} секунд...")
    await asyncio.sleep(first_delay)
    await publish_post()
    
    post_count = 1
    
    while True:
        next_interval = random.randint(MIN_INTERVAL, MAX_INTERVAL)
        hours = next_interval // 3600
        minutes = (next_interval % 3600) // 60
        
        logger.info(f"⏳ Следующий пост через {hours}ч {minutes}м")
        logger.info(f"📅 Ожидаемое время: {(datetime.now() + timedelta(seconds=next_interval)).strftime('%H:%M:%S')}")
        
        await asyncio.sleep(next_interval)
        await publish_post()
        post_count += 1
        
        logger.info(f"📊 Всего опубликовано постов: {post_count}")
