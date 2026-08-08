"""Сборка поста и рассылка: подбор медиа, отправка себе и подписчикам."""
import asyncio
import logging
import random
import time
from typing import Optional

from ..config import CHANNEL_ID, OWNER_ID, DEEPSEEK_API_KEY, SEND_DELAY
from ..storage import (load_users, save_users, load_history, save_history,
                       history)
from ..content.deepseek import generate_caption_with_validation
from ..content.vision import analyze_photo_for_comment
from ..content.media import get_streamer_media, get_random_photo
from ..content.streamers import get_streamer_display_name
from ..content.text import clean_text, truncate_by_sentences
from .client import bot
from .sender import send_post_with_retry
from .media import send_media_message

logger = logging.getLogger(__name__)

async def get_channel_id() -> Optional[str]:
    """Возвращает CHANNEL_ID из окружения.

    Прежняя автоподстановка канала вызывала bot.get_updates() параллельно
    работающему long polling — Telegram отвечает на это ошибкой 409
    (terminated by other getUpdates request) и рвёт поллинг. Канал теперь
    задаётся только переменной CHANNEL_ID.
    """
    if CHANNEL_ID and CHANNEL_ID.strip():
        return CHANNEL_ID.strip()
    return None

async def resolve_post_media(streamer_key: Optional[str]):
    """Подбирает медиа для поста: клип/скрин стримера, фото стримера, фото Азии."""
    if streamer_key:
        media_url, media_type = await asyncio.to_thread(
            get_streamer_media, streamer_key, get_streamer_display_name(streamer_key)
        )
        if media_type == 'clip':
            return media_url, media_type

    photo_url = await get_random_photo("streamer", None)
    if photo_url:
        return photo_url, 'photo'

    photo_url = await get_random_photo("asia", None)
    if photo_url:
        return photo_url, 'photo'

    return None, None

async def create_post_with_photo(chat_id, user_id=0, skip_moderation=False, style="streamer"):
    try:
        # Генерация делает до 20 последовательных запросов к DeepSeek по 60 с —
        # выполнение в потоке, чтобы не вешать весь бот.
        caption, streamer_key = await asyncio.to_thread(generate_caption_with_validation)
        if not caption:
            return False

        media_url, media_type = await resolve_post_media(streamer_key)

        if not media_url:
            logger.error("❌ Не удалось найти медиа")
            await send_post_with_retry(chat_id, None, caption, "text")
            return True
        
        if media_type == 'photo' and random.random() < 0.1 and DEEPSEEK_API_KEY:
            photo_comment = await analyze_photo_for_comment(media_url)
            if photo_comment:
                caption = caption.rstrip() + "\n\n" + photo_comment

        if media_type == 'photo' and media_url not in history:
            history.append(media_url)
            save_history(history)

        await send_post_with_retry(chat_id, media_url, caption, media_type)
        logger.info(f"✅ Пост отправлен в {chat_id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания поста: {e}")
        return False

async def send_to_all_users():
    try:
        users_list = load_users()
        if not users_list:
            logger.warning("Нет пользователей для отправки")
            return
        
        logger.info(f"Отправка поста {len(users_list)} пользователям...")
        
        caption, streamer_key = await asyncio.to_thread(generate_caption_with_validation)
        if not caption:
            return

        media_url, media_type = await resolve_post_media(streamer_key)

        if not media_url:
            logger.error("Не удалось найти медиа")
            return
        
        # Отправляем в канал
        channel_id = CHANNEL_ID or await get_channel_id()
        if channel_id:
            try:
                logger.info(f"📢 Отправка в канал {channel_id}")
                await send_post_with_retry(channel_id, media_url, caption, media_type)
                logger.info(f"✅ Пост отправлен в канал {channel_id}")
            except Exception as e:
                logger.error(f"❌ Ошибка отправки в канал: {e}")
        else:
            logger.info("ℹ️ Канал не найден, отправка только пользователям")
        
        # Отправляем пользователям
        sent_count = 0
        failed_count = 0
        random.shuffle(users_list)
        
        for i, chat_id in enumerate(users_list):
            try:
                logger.info(f"📨 Отправка пользователю {i+1}/{len(users_list)}: {chat_id}")
                await send_post_with_retry(chat_id, media_url, caption, media_type)
                sent_count += 1
                
                if i < len(users_list) - 1:
                    await asyncio.sleep(SEND_DELAY)
                    
            except Exception as e:
                logger.error(f"Ошибка отправки пользователю {chat_id}: {e}")
                failed_count += 1
        
        logger.info(f"✅ Пост отправлен: {sent_count} пользователям, {failed_count} ошибок")
    except Exception as e:
        logger.error(f"Ошибка в send_to_all_users: {e}")
