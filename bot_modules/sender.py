"""Модуль для отправки сообщений с повторными попытками."""
import asyncio
import logging
from typing import Optional, Union
from telegram import Message, PhotoSize, Video, Animation, Document, InputFile
from bot_modules.client import bot  # <-- ИСПРАВЛЕНО!

logger = logging.getLogger(__name__)


async def send_post_with_retry(
    chat_id: int,
    text: Optional[str] = None,
    photo: Optional[Union[str, bytes, PhotoSize, InputFile]] = None,
    video: Optional[Union[str, bytes, Video, InputFile]] = None,
    animation: Optional[Union[str, bytes, Animation, InputFile]] = None,
    document: Optional[Union[str, bytes, Document, InputFile]] = None,
    caption: Optional[str] = None,
    parse_mode: Optional[str] = "Markdown",
    disable_notification: bool = False,
    reply_to_message_id: Optional[int] = None,
    max_retries: int = 3,
    retry_delay: int = 5,
) -> Optional[Message]:
    """
    Отправляет сообщение с повторными попытками при ошибках.
    """
    for attempt in range(max_retries):
        try:
            if photo:
                message = await bot.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    caption=caption or text,
                    parse_mode=parse_mode,
                    disable_notification=disable_notification,
                    reply_to_message_id=reply_to_message_id,
                )
            elif video:
                message = await bot.send_video(
                    chat_id=chat_id,
                    video=video,
                    caption=caption or text,
                    parse_mode=parse_mode,
                    disable_notification=disable_notification,
                    reply_to_message_id=reply_to_message_id,
                )
            elif animation:
                message = await bot.send_animation(
                    chat_id=chat_id,
                    animation=animation,
                    caption=caption or text,
                    parse_mode=parse_mode,
                    disable_notification=disable_notification,
                    reply_to_message_id=reply_to_message_id,
                )
            elif document:
                message = await bot.send_document(
                    chat_id=chat_id,
                    document=document,
                    caption=caption or text,
                    parse_mode=parse_mode,
                    disable_notification=disable_notification,
                    reply_to_message_id=reply_to_message_id,
                )
            else:
                message = await bot.send_message(
                    chat_id=chat_id,
                    text=text or caption or "",
                    parse_mode=parse_mode,
                    disable_notification=disable_notification,
                    reply_to_message_id=reply_to_message_id,
                )
            
            logger.info(f"✅ Сообщение отправлено в чат {chat_id}")
            return message
            
        except Exception as e:
            logger.warning(f"⚠️ Попытка {attempt + 1}/{max_retries} не удалась: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"❌ Все попытки отправки в чат {chat_id} провалились")
                return None
    
    return None
