"""Планировщик для публикации мемов (скачивание и отправка)."""
import asyncio
import logging
import random
import io
import time
from datetime import datetime, timedelta
from typing import Optional  # <--- ДОБАВЛЯЕМ ЭТУ СТРОКУ

import requests
from config import CHANNEL_ID
from content.meme_forwarder import get_random_meme_to_forward
from telegram.client import bot

logger = logging.getLogger(__name__)

MIN_INTERVAL = 3600
MAX_INTERVAL = 10800

def download_media(url: str) -> Optional[io.BytesIO]:
    """Скачивает медиа по ссылке в память."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, timeout=30, headers=headers)
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            if 'image' in content_type or 'video' in content_type or 'gif' in content_type:
                return io.BytesIO(response.content)
            if len(response.content) > 10000:
                return io.BytesIO(response.content)
        return None
    except Exception as e:
        logger.error(f"Ошибка скачивания: {e}")
        return None

def get_direct_media_url(post_url: str) -> Optional[str]:
    """Пытается получить прямую ссылку на медиа из поста."""
    try:
        response = requests.get(post_url, timeout=10)
        if response.status_code != 200:
            return None
        
        import re
        patterns = [
            r'https?://[^\s]+\.(jpg|jpeg|png|gif|mp4|webm|webp)[^\s]*',
            r'https?://[^\s]+/file/[^\s]+',
            r'https?://cdn[^\s]+\.(jpg|jpeg|png|gif|mp4)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, response.text)
            if matches:
                return matches[0]
        return None
    except Exception as e:
        logger.error(f"Ошибка получения прямой ссылки: {e}")
        return None

async def send_meme_to_channel() -> bool:
    """Скачивает и отправляет мем в канал."""
    try:
        meme_data = get_random_meme_to_forward()
        if not meme_data:
            logger.warning("⚠️ Нет доступных мемов")
            return False
        
        source_channel = meme_data.get('source_channel')
        message_id = meme_data.get('message_id')
        source_name = meme_data.get('source_name')
        
        if not source_channel or not message_id:
            return False
        
        logger.info(f"📥 Обрабатываю мем из {source_name} (ID: {message_id})")
        
        post_url = f"https://t.me/{source_channel.replace('@', '')}/{message_id}"
        logger.info(f"🔗 Загружаю страницу поста: {post_url}")
        
        direct_url = get_direct_media_url(post_url)
        if not direct_url:
            logger.warning(f"⚠️ Не найдена прямая ссылка на медиа в посте {message_id}")
            return False
        
        logger.info(f"📥 Скачиваю медиа: {direct_url[:80]}...")
        
        media_data = download_media(direct_url)
        if not media_data:
            logger.warning(f"⚠️ Не удалось скачать медиа")
            return False
        
        url_lower = direct_url.lower()
        if any(ext in url_lower for ext in ['.jpg', '.jpeg', '.png', '.webp']):
            media_type = 'photo'
        elif any(ext in url_lower for ext in ['.mp4', '.mov', '.avi']):
            media_type = 'video'
        elif any(ext in url_lower for ext in ['.gif', '.webm']):
            media_type = 'animation'
        else:
            media_type = 'document'
        
        ext = direct_url.split('.')[-1].split('?')[0][:4]
        filename = f"meme_{int(time.time())}.{ext}"
        
        logger.info(f"📤 Отправляю {media_type} ({len(media_data.getvalue()) // 1024}KB)")
        
        if media_type == 'photo':
            await bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=media_data,
                filename=filename
            )
        elif media_type == 'video':
            await bot.send_video(
                chat_id=CHANNEL_ID,
                video=media_data,
                filename=filename
            )
        elif media_type == 'animation':
            await bot.send_animation(
                chat_id=CHANNEL_ID,
                animation=media_data,
                filename=filename
            )
        else:
            await bot.send_document(
                chat_id=CHANNEL_ID,
                document=media_data,
                filename=filename
            )
        
        logger.info(f"✅ Мем из {source_name} опубликован!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        return False

async def meme_scheduler():
    """Цикл планировщика мемов."""
    logger.info("=" * 60)
    logger.info("🎬 ПЛАНИРОВЩИК МЕМОВ ЗАПУЩЕН")
    logger.info(f"📡 Канал: {CHANNEL_ID}")
    logger.info(f"⏱️ Интервал: 1-3 часа")
    logger.info("📦 Источники: videos_dolboyoba, shitcollection, postleftism, noviop")
    logger.info("🔄 Режим: скачивание и отправка")
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
