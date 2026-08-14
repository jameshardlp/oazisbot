"""Планировщик для автоматической публикации постов."""
import asyncio
import logging
from datetime import datetime

from config import CHANNEL_ID, MIN_POST_INTERVAL
from content.deepseek import generate_caption_with_validation
from content.media import get_streamer_media
from telegram.client import bot

logger = logging.getLogger(__name__)

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
        
        # Ищем медиа для стримера
        media_url = None
        media_type = None
        
        if streamer_key:
            logger.info(f"🔍 Ищу медиа для стримера: {streamer_key}")
            media_url, media_type = get_streamer_media(streamer_key, streamer_key)
            if media_url:
                logger.info(f"✅ Найдено медиа: {media_type}")
            else:
                logger.info("ℹ️ Медиа не найдено, отправляю только текст")
        
        # Публикуем в канал
        if CHANNEL_ID:
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
        else:
            logger.warning("⚠️ CHANNEL_ID не задан, пост не отправлен")
            
    except Exception as e:
        logger.error(f"❌ Ошибка публикации поста: {e}")

async def scheduler():
    """Основной цикл планировщика."""
    logger.info(f"⏰ Планировщик запущен. Интервал: {MIN_POST_INTERVAL} секунд")
    logger.info(f"📡 Канал для публикации: {CHANNEL_ID}")
    
    # Публикуем первый пост через 10 секунд после запуска
    await asyncio.sleep(10)
    await publish_post()
    
    while True:
        await asyncio.sleep(MIN_POST_INTERVAL)
        await publish_post()
