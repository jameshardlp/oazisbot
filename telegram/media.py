"""Отправка медиа любых поддерживаемых типов + пометка карточки модерации."""
import logging

from aiogram.types import Message

from client import bot

logger = logging.getLogger(__name__)

# Медиа, которые Telegram отправляет без подписи
CAPTIONLESS_MEDIA = ("sticker", "video_note")

async def send_media_message(chat_id, media_type, file_id, caption=None, reply_markup=None, parse_mode=None):
    """Единая отправка медиа любого поддерживаемого типа.

    Для стикеров и видео-кружков подпись невозможна, поэтому текст уходит
    отдельным сообщением. Раньше эти два типа в рассылке терялись: они
    попадали в ветку else и заменялись обычным текстом.
    """
    senders = {
        "photo": (bot.send_photo, "photo"),
        "video": (bot.send_video, "video"),
        "animation": (bot.send_animation, "animation"),
        "audio": (bot.send_audio, "audio"),
        "document": (bot.send_document, "document"),
        "voice": (bot.send_voice, "voice"),
        "sticker": (bot.send_sticker, "sticker"),
        "video_note": (bot.send_video_note, "video_note"),
    }

    if not file_id or media_type not in senders:
        if caption:
            await bot.send_message(chat_id=chat_id, text=caption,
                                   reply_markup=reply_markup, parse_mode=parse_mode)
        return

    sender, kwarg = senders[media_type]

    if media_type in CAPTIONLESS_MEDIA:
        await sender(chat_id=chat_id, **{kwarg: file_id})
        if caption:
            await bot.send_message(chat_id=chat_id, text=caption,
                                   reply_markup=reply_markup, parse_mode=parse_mode)
        elif reply_markup:
            await bot.send_message(chat_id=chat_id, text="⬆️ Медиафайл",
                                   reply_markup=reply_markup)
        return

    kwargs = {
        "chat_id": chat_id,
        kwarg: file_id,
        "caption": caption or None,
        "reply_markup": reply_markup,
        "parse_mode": parse_mode,
    }
    # Удаляем None значения, чтобы не передавать лишние параметры
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    await sender(**kwargs)

async def mark_moderation_card(message: Message, verdict: str):
    """Дописывает вердикт в карточку модерации и убирает кнопки.

    Карточка может быть и текстом, и медиа с подписью — у медиа message.text
    равен None, поэтому edit_text на нём падал и рассылка не публиковалась.
    """
    try:
        if message.text is not None:
            await message.edit_text(message.text + verdict, reply_markup=None)
        elif message.caption is not None:
            await message.edit_caption(caption=message.caption + verdict, reply_markup=None)
        else:
            await message.edit_reply_markup(reply_markup=None)
    except Exception as e:
        logger.error(f"Не удалось обновить карточку модерации: {e}")
