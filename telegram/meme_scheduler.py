"""Планировщик для публикации мемов (копирование сообщений)."""
import asyncio
import logging
import random
from datetime import datetime, timedelta

from config import CHANNEL_ID
from content.meme_forwarder import get_random_meme_to_forward
from telegram.client import bot

logger = logging.getLogger(__name__)

MIN_INTERVAL = 3600
MAX_INTERVAL = 10800

async def send_meme_to_channel() -> bool:
    """Копирует мем в канал (без упоминания источника)."""
    try:
        # Получаем данные для копирования
        meme_data = get_random_meme_to_forward()
        if not meme_data:
            logger.warning("⚠️ Нет доступных мемов")
            return False
        
        source_channel = meme_data.get('source_channel')
        message_id = meme_data.get('message_id')
        
        if not source_channel or not message_id:
            return False
        
        logger.info(f"📤 Копирую мем из {source_channel} (ID: {message_id})")
        
        # Используем copy_message вместо forward_message
        # copy_message создаёт копию сообщения без ссылки на оригинал
        await bot.copy_message(
            chat_id=CHANNEL_ID,
            from_chat_id=source_channel,
            message_id=message_id
        )
        
        logger.info("✅ Мем опубликован!")
        return True
        
    except Exception as e:
        error_msg = str(e).lower()
        if "not found" in error_msg:
            logger.warning(f"⚠️ Сообщение {message_id} не найдено")
        elif "chat not found" in error_msg:
            logger.warning(f"⚠️ Канал {source_channel} не доступен для копирования")
        else:
            logger.error(f"❌ Ошибка копирования: {e}")
        return False

async def meme_scheduler():
    """Цикл планировщика мемов."""
    logger.info("=" * 60)
    logger.info("🎬 ПЛАНИРОВЩИК МЕМОВ ЗАПУЩЕН")
    logger.info(f"📡 Канал: {CHANNEL_ID}")
    logger.info(f"⏱️ Интервал: 1-3 часа")
    logger.info("📦 Источники: videos_dolboyoba, shitcollection, postleftism, noviop")
    logger.info("=" * 60)
    
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
        await asyncio.sleep(next_interval)
        
        success = await send_meme_to_channel()
        if success:
            count += 1
            logger.info(f"📊 Всего опубликовано мемов: {count}")
        else:
            logger.warning("⚠️ Публикация мема не удалась, пробую дальше...")
