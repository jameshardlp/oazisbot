"""Модуль для отправки медиа-сообщений."""
import logging
from typing import Optional, Union
from telegram import InputFile, Message, PhotoSize, Video, Animation, Document
from bot_modules.client import bot  # <-- ИСПРАВЛЕНО!

logger = logging.getLogger(__name__)


async def send_media_message(
    chat_id: int,
    media_type: str,
    media_file: Union[str, bytes, PhotoSize, Video, Animation, Document, InputFile],
    caption: Optional[str] = None,
    parse_mode: Optional[str] = "Markdown",
    disable_notification: bool = False,
) -> Optional[Message]:
    """
    Отправляет медиа-сообщение в зависимости от типа.
    """
    try:
        if media_type == 'photo':
            message = await bot.send_photo(
                chat_id=chat_id,
                photo=media_file,
                caption=caption,
                parse_mode=parse_mode,
                disable_notification=disable_notification,
            )
        elif media_type == 'video':
            message = await bot.send_video(
                chat_id=chat_id,
                video=media_file,
                caption=caption,
                parse_mode=parse_mode,
                disable_notification=disable_notification,
            )
        elif media_type == 'animation':
            message = await bot.send_animation(
                chat_id=chat_id,
                animation=media_file,
                caption=caption,
                parse_mode=parse_mode,
                disable_notification=disable_notification,
            )
        elif media_type == 'document':
            message = await bot.send_document(
                chat_id=chat_id,
                document=media_file,
                caption=caption,
                parse_mode=parse_mode,
                disable_notification=disable_notification,
            )
        else:
            logger.warning(f"⚠️ Неизвестный тип медиа: {media_type}")
            return None
        
        logger.info(f"✅ Медиа отправлено в чат {chat_id}")
        return message
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки медиа: {e}")
        return None
