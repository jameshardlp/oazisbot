"""Отправка постов с ретраями и антифлуд-задержкой."""
import re
import logging
import asyncio
import time
from collections import defaultdict

from aiogram.exceptions import TelegramAPIError

from ..config import SEND_DELAY
from ..storage import load_users, save_users
from ..content.deepseek import generate_caption_with_validation
from ..content.text import clean_text, truncate_by_sentences
from .client import bot

logger = logging.getLogger(__name__)

last_user_message_time = defaultdict(float)

async def send_post_with_retry(chat_id, photo_url=None, caption=None, media_type='photo', max_retries=3):
    current_time = time.time()
    last_time = last_user_message_time.get(chat_id, 0)
    time_since_last = current_time - last_time

    if time_since_last < SEND_DELAY:
        wait_time = SEND_DELAY - time_since_last
        logger.info(f"⏳ Ожидание {wait_time:.1f} сек перед отправкой пользователю {chat_id}")
        await asyncio.sleep(wait_time)
    
    last_user_message_time[chat_id] = time.time()
    
    for attempt in range(max_retries):
        try:
            if not photo_url and not caption:
                return False
            
            if not photo_url:
                if caption:
                    await bot.send_message(chat_id=chat_id, text=caption)
                return True
            
            if not caption:
                caption, _ = await asyncio.to_thread(generate_caption_with_validation)
                caption = clean_text(caption)
                caption = truncate_by_sentences(caption, max_length=1023)
            
            if media_type == 'clip':
                text = f"{caption}\n\n{photo_url}"
                await bot.send_message(chat_id=chat_id, text=text)
            elif media_type == 'text':
                await bot.send_message(chat_id=chat_id, text=caption)
            else:
                if len(caption) > 1024:
                    caption = truncate_by_sentences(caption, max_length=1023)
                await bot.send_photo(chat_id=chat_id, photo=photo_url, caption=caption)
            
            return True
            
        except TelegramAPIError as e:
            error_str = str(e).lower()

            if "too many requests" in error_str or "retry after" in error_str:
                match = re.search(r"retry after (\d+)", str(e))
                if match:
                    wait_time = int(match.group(1)) + 1
                else:
                    wait_time = 5 * (attempt + 1)
                
                logger.warning(f"⚠️ Лимит превышен для {chat_id}. Ожидание {wait_time} сек. Попытка {attempt+1}/{max_retries}")
                await asyncio.sleep(wait_time)
                continue
                
            elif "forbidden" in error_str or "chat not found" in error_str:
                users_list = load_users()
                if chat_id in users_list:
                    users_list.remove(chat_id)
                    save_users(users_list)
                    logger.info(f"👤 Пользователь {chat_id} удалён")
                return False
            else:
                logger.error(f"❌ Ошибка Telegram при отправке в {chat_id}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
                    continue
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка отправки в {chat_id}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
                continue
            return False
    
    return False
