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
        logger.info(f"📎 URL: {media_url[:80]}...")
        
        # Отправляем в зависимости от типа
        try:
            if media_type == 'photo':
                await bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=media_url,
                    # Не добавляем подпись
                )
            elif media_type == 'video':
                await bot.send_video(
                    chat_id=CHANNEL_ID,
                    video=media_url,
                )
            elif media_type == 'animation':
                await bot.send_animation(
                    chat_id=CHANNEL_ID,
                    animation=media_url,
                )
            else:
                # Пробуем отправить как документ
                await bot.send_document(
                    chat_id=CHANNEL_ID,
                    document=media_url,
                )
            
            logger.info(f"✅ Мем (ID: {post_id}) опубликован в канал!")
            return True
            
        except Exception as e:
            error_msg = str(e).lower()
            if "failed to get http url content" in error_msg:
                logger.warning(f"⚠️ URL недоступен: {media_url[:50]}...")
                # URL недоступен, удаляем из кэша
                from content.meme_parser import _meme_parser
                if _meme_parser:
                    _meme_parser.media_cache = [
                        m for m in _meme_parser.media_cache 
                        if m.get('media_url') != media_url
                    ]
                    logger.info("🗑️ Недоступный мем удалён из кэша")
                return False
            else:
                logger.error(f"❌ Ошибка отправки: {e}")
                return False
        
    except Exception as e:
        logger.error(f"❌ Ошибка публикации мема: {e}")
        return False

async def meme_scheduler():
    """Цикл планировщика мемов."""
    logger.info("=" * 60)
    logger.info("🎬 ПЛАНИРОВЩИК МЕМОВ ЗАПУЩЕН")
    logger.info(f"📡 Канал: {CHANNEL_ID}")
    logger.info(f"⏱️ Интервал: {MIN_INTERVAL // 3600}-{MAX_INTERVAL // 3600} часа")
    logger.info("📦 Источники: videos_dolboyoba, shitcollection, postleftism, noviop")
    logger.info("=" * 60)
    
    # Первый мем через 30-60 секунд
    first_delay = random.randint(30, 60)
    logger.info(f"⏳ Первый мем через {first_delay} секунд...")
    await asyncio.sleep(first_delay)
    await send_meme_to_channel()
    
    count = 1
    
    while True:
        next_interval = random.randint(MIN_INTERVAL, MAX_INTERVAL)
        hours = next_interval // 3600
        minutes = (next_interval % 3600) // 60
        
        logger.info(f"⏳ Следующий мем через {hours}ч {minutes}м")
        next_time = datetime.now() + timedelta(seconds=next_interval)
        logger.info(f"📅 Ожидаемое время: {next_time.strftime('%H:%M:%S')}")
        
        await asyncio.sleep(next_interval)
        
        success = await send_meme_to_channel()
        if success:
            count += 1
            logger.info(f"📊 Всего опубликовано мемов: {count}")
        else:
            logger.warning("⚠️ Публикация мема не удалась, пробую дальше...")
