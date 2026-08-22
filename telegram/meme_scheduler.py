"""Планировщик для публикации мемов (скачивание и отправка)."""
import asyncio
import logging
import random
import io
import time
import re
from datetime import datetime, timedelta
from typing import Optional

import requests
from config import CHANNEL_ID
from content.meme_forwarder import get_random_meme_to_forward
from telegram.client import bot

logger = logging.getLogger(__name__)

MIN_INTERVAL = 3600
MAX_INTERVAL = 10800

def download_media(url: str) -> Optional[io.BytesIO]:
    """Скачивает медиа по ссылке в память."""
    if not url or not url.startswith('http'):
        logger.warning(f"⚠️ Невалидный URL: {url}")
        return None

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, timeout=30, headers=headers)
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            if any(t in content_type for t in ['image', 'video', 'gif']):
                return io.BytesIO(response.content)
            # Если content-type неизвестен, но это похоже на файл
            if len(response.content) > 10000:  # больше 10KB
                return io.BytesIO(response.content)
        return None
    except Exception as e:
        logger.error(f"Ошибка скачивания: {e}")
        return None

def get_direct_media_url(post_url: str) -> Optional[str]:
    """Пытается получить прямую ссылку на медиа из поста."""
    try:
        response = requests.get(post_url, timeout=15, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        if response.status_code != 200:
            logger.warning(f"⚠️ Не удалось загрузить страницу поста: {response.status_code}")
            return None

        html = response.text

        # 1. Ищем прямые ссылки на файлы через теги <img> и <video>
        img_pattern = r'<img[^>]+src="(https?://[^"]+\.(?:jpg|jpeg|png|gif|webp))"'
        img_matches = re.findall(img_pattern, html, re.IGNORECASE)
        if img_matches:
            # Выбираем самое большое изображение (обычно последнее в списке)
            return img_matches[-1]

        video_pattern = r'<video[^>]+src="(https?://[^"]+\.(?:mp4|webm|mov))"'
        video_matches = re.findall(video_pattern, html, re.IGNORECASE)
        if video_matches:
            return video_matches[0]

        # 2. Ищем ссылки на файлы через data-bem (как в парсере @maddysontg)
        bem_pattern = r'data-bem="({[^"]+})"'
        bem_matches = re.findall(bem_pattern, html)
        for bem_json in bem_matches:
            try:
                import json
                data = json.loads(bem_json)
                if 'photo' in data and 'src' in data['photo']:
                    src = data['photo']['src']
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/'):
                        src = 'https://t.me' + src
                    if '/preview/' in src:
                        src = src.replace('/preview/', '/file/')
                    return src
            except:
                pass

        # 3. Ищем любые ссылки с расширениями файлов в тексте
        file_pattern = r'https?://[^\s"\']+\.(?:jpg|jpeg|png|gif|mp4|webm|webp)'
        file_matches = re.findall(file_pattern, html, re.IGNORECASE)
        if file_matches:
            return file_matches[0]

        # 4. Ищем ссылки через Telegram file
        tg_file_pattern = r'https?://t\.me/[^/]+/\d+'
        tg_file_matches = re.findall(tg_file_pattern, html)
        if tg_file_matches:
            # Пробуем загрузить страницу поста и найти там изображение
            for tg_url in tg_file_matches:
                return get_direct_media_url(tg_url)  # Рекурсивно пробуем

        logger.warning(f"⚠️ Не найдена прямая ссылка на медиа в посте {post_url}")
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

        # Определяем тип по расширению
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
