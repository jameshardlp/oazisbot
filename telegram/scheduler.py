"""Планировщик для автоматической публикации постов."""
import asyncio
import logging
import random
from datetime import datetime, timedelta

from config import CHANNEL_ID
from content.deepseek import generate_caption_with_validation
from content.media import get_streamer_media
from telegram.client import bot

logger = logging.getLogger(__name__)

# ===== НАСТРОЙКИ ИНТЕРВАЛА =====
MIN_INTERVAL_HOURS = 1
MAX_INTERVAL_HOURS = 3

MIN_INTERVAL = MIN_INTERVAL_HOURS * 3600  # 1 час в секундах
MAX_INTERVAL = MAX_INTERVAL_HOURS * 3600  # 3 часа в секундах

# Минимум постов в день при таком интервале:
# 24 часа / 3 часа (макс) = 8 постов в день минимум
# 24 часа / 1 час (мин) = 24 поста в день максимум
MIN_POSTS_PER_DAY = 24 // MAX_INTERVAL_HOURS  # 8 постов в день

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
    """Основной цикл планировщика с интервалом 1-3 часа."""
    logger.info("=" * 60)
    logger.info("⏰ ПЛАНИРОВЩИК ЗАПУЩЕН")
    logger.info(f"📊 Минимум постов в день: {MIN_POSTS_PER_DAY}")
    logger.info(f"⏱️ Интервал между постами: от {MIN_INTERVAL_HOURS} до {MAX_INTERVAL_HOURS} часов")
    logger.info(f"📡 Канал для публикации: {CHANNEL_ID}")
    logger.info("=" * 60)
    
    # Публикуем первый пост через 10-30 секунд после запуска
    first_delay = random.randint(10, 30)
    logger.info(f"⏳ Первый пост через {first_delay} секунд...")
    await asyncio.sleep(first_delay)
    await publish_post()
    
    # Счётчик постов для статистики
    post_count = 1
    last_post_time = datetime.now()
    
    while True:
        # Вычисляем следующий интервал (1-3 часа)
        next_interval = random.randint(MIN_INTERVAL, MAX_INTERVAL)
        
        # Логируем следующий пост
        next_post_time = datetime.now() + timedelta(seconds=next_interval)
        hours = next_interval // 3600
        minutes = (next_interval % 3600) // 60
        logger.info(f"⏳ Следующий пост через {hours}ч {minutes}м")
        logger.info(f"📅 Ожидаемое время: {next_post_time.strftime('%H:%M:%S')}")
        
        await asyncio.sleep(next_interval)
        await publish_post()
        
        post_count += 1
        last_post_time = datetime.now()
        
        # Статистика
        logger.info(f"📊 Всего опубликовано постов: {post_count}")
        
        # Проверяем, достаточно ли постов за день
        now = datetime.now()
        if post_count >= MIN_POSTS_PER_DAY:
            logger.info(f"✅ Норма {MIN_POSTS_PER_DAY} постов в день выполнена!")
        else:
            remaining = MIN_POSTS_PER_DAY - post_count
            hours_left = 24 - now.hour - 1
            if hours_left > 0 and remaining > 0:
                logger.info(f"📊 Осталось постов до нормы: {remaining}")
