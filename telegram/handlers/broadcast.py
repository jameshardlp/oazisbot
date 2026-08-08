"""Команда /broadcast: приём материала и выбор способа оплаты."""
import logging
import time

from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from ...config import OWNER_ID
from ...storage import load_users
from ...payments.orders import broadcast_data, broadcast_prices
from ..client import dp
from ..media import send_media_message

logger = logging.getLogger(__name__)

@dp.message(Command("broadcast"))
async def broadcast_command(message: Message):
    try:
        if message.chat.type != "private":
            await message.answer("ℹ️ Эта команда работает только в личных сообщениях с ботом.")
            return
        
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        text = ""
        has_media = False
        media_type = None
        media_file_id = None
        
        if message.text:
            text = message.text.replace("/broadcast", "").strip()
        elif message.caption:
            text = message.caption.replace("/broadcast", "").strip()
        
        if message.photo:
            has_media = True
            media_type = "photo"
            media_file_id = message.photo[-1].file_id
            if not text and message.caption:
                text = message.caption.replace("/broadcast", "").strip()
        elif message.video:
            has_media = True
            media_type = "video"
            media_file_id = message.video.file_id
            if not text and message.caption:
                text = message.caption.replace("/broadcast", "").strip()
        elif message.document:
            has_media = True
            media_type = "document"
            media_file_id = message.document.file_id
            if not text and message.caption:
                text = message.caption.replace("/broadcast", "").strip()
        elif message.animation:
            has_media = True
            media_type = "animation"
            media_file_id = message.animation.file_id
            if not text and message.caption:
                text = message.caption.replace("/broadcast", "").strip()
        elif message.audio:
            has_media = True
            media_type = "audio"
            media_file_id = message.audio.file_id
            if not text and message.caption:
                text = message.caption.replace("/broadcast", "").strip()
        elif message.voice:
            has_media = True
            media_type = "voice"
            media_file_id = message.voice.file_id
            if not text and message.caption:
                text = message.caption.replace("/broadcast", "").strip()
        elif message.video_note:
            has_media = True
            media_type = "video_note"
            media_file_id = message.video_note.file_id
            text = ""
        elif message.sticker:
            has_media = True
            media_type = "sticker"
            media_file_id = message.sticker.file_id
            text = ""
        
        if not text and not has_media:
            stars_price = broadcast_prices.get("stars", 100)
            rub_price = broadcast_prices.get("rub", 100)
            await message.answer(
                f"📢 **Платная рассылка**\n\n"
                f"Отправьте сообщение с текстом или медиафайлом.\n\n"
                f"💰 Цена: {stars_price} ⭐ или {rub_price} RUB\n"
                f"💳 После оплаты сообщение уйдёт на модерацию.\n\n"
                f"📌 Поддерживаются: фото, видео, GIF, аудио, документы, голосовые, стикеры.",
                parse_mode="Markdown"
            )
            return
        
        stars_price = broadcast_prices.get("stars", 100)
        rub_price = broadcast_prices.get("rub", 100)
        order_id = f"broadcast_{user_id}_{int(time.time())}"
        
        broadcast_data[user_id] = {
            'text': text,
            'has_media': has_media,
            'media_type': media_type,
            'media_file_id': media_file_id,
            'timestamp': time.time(),
            'chat_id': chat_id,
            'user_id': user_id,
            'order_id': order_id,
            'paid': False
        }
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"⭐ Оплатить {stars_price} звёзд", callback_data=f"pay_stars_{order_id}")],
            [InlineKeyboardButton(text=f"💳 Оплатить {rub_price} RUB", callback_data=f"pay_rub_{order_id}")],
            [InlineKeyboardButton(text=f"🔗 Оплатить через AuraPay", callback_data=f"pay_aurapay_{order_id}")]
        ])
        
        preview_text = f"📢 **Ваше сообщение для рассылки**\n\n"
        if text:
            preview_text += f"📝 {text[:200]}{'...' if len(text) > 200 else ''}\n\n"
        else:
            preview_text += f"📝 (без текста)\n\n"
        
        if has_media:
            media_names = {
                "photo": "📸 Фото",
                "video": "🎬 Видео",
                "document": "📄 Документ",
                "animation": "🎥 GIF",
                "audio": "🎵 Аудио",
                "voice": "🎤 Голосовое",
                "video_note": "🔄 Видео-кружок",
                "sticker": "🎯 Стикер"
            }
            preview_text += f"📎 {media_names.get(media_type, 'Медиафайл')} (будет отправлено)\n\n"
        
        preview_text += f"💰 Цена: {stars_price} ⭐ или {rub_price} RUB\n"
        preview_text += f"⏳ После оплаты сообщение уйдёт на модерацию."
        
        if has_media and media_file_id:
            await send_media_message(message.chat.id, media_type, media_file_id,
                                     caption=preview_text, reply_markup=keyboard,
                                     parse_mode="Markdown")
        else:
            await message.answer(
                preview_text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        
        logger.info(f"📢 Рассылка создана для {user_id}, заказ {order_id}")
        
    except Exception as e:
        logger.error(f"Ошибка в команде broadcast: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")
