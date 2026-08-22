"""Обработчик команды /photo для отправки случайного фото стримера."""
import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler
from content.media import get_streamer_photo
from content.streamers import STREAMER_KEYS, STREAMER_DISPLAY_NAMES

logger = logging.getLogger(__name__)


async def photo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /photo — отправляет случайное фото стримера."""
    user_id = update.effective_user.id
    
    # Выбираем случайного стримера
    streamer_key = random.choice(STREAMER_KEYS)
    streamer_name = STREAMER_DISPLAY_NAMES.get(streamer_key, streamer_key)
    
    await update.message.reply_text(f"🔍 Ищу фото для {streamer_name}...")
    
    # Ищем фото
    photo_url = get_streamer_photo(streamer_key)
    
    if photo_url:
        await update.message.reply_photo(
            photo=photo_url,
            caption=f"📸 {streamer_name}"
        )
    else:
        await update.message.reply_text(
            f"❌ Не удалось найти фото для {streamer_name}. Попробуйте позже."
        )


def register_photo_handler(app):
    """Регистрирует обработчик команды /photo."""
    app.add_handler(CommandHandler("photo", photo_command))