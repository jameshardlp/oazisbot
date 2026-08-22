"""Обработчик команды /resend для отправки контента в канал от имени бота."""
import logging
from typing import Optional

# Импорты из установленной библиотеки python-telegram-bot
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters

from config import OWNER_ID, CHANNEL_ID
from bot_modules.client import bot

logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
AWAITING_CONTENT = 1


async def resend_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик команды /resend.
    Только для владельца бота.
    """
    user_id = update.effective_user.id
    
    # Проверяем, что пользователь — владелец
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ У вас нет прав на использование этой команды.")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "📤 *Режим отправки в канал*\n\n"
        "Отправьте мне контент для публикации в канал:\n"
        "• Текст\n"
        "• Фото с подписью\n"
        "• Видео с подписью\n"
        "• GIF с подписью\n"
        "• Документ с подписью\n\n"
        "❌ Для отмены отправьте /cancel",
        parse_mode="Markdown"
    )
    
    return AWAITING_CONTENT


async def handle_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик полученного контента.
    Отправляет его в канал.
    """
    user_id = update.effective_user.id
    message = update.message
    
    # Проверяем права
    if user_id != OWNER_ID:
        await message.reply_text("❌ У вас нет прав.")
        return ConversationHandler.END
    
    # Проверяем, что есть контент
    if not message.text and not message.photo and not message.video and not message.animation and not message.document:
        await message.reply_text(
            "⚠️ Пожалуйста, отправьте текст, фото, видео, GIF или документ."
        )
        return AWAITING_CONTENT
    
    try:
        # Отправляем в канал
        if not CHANNEL_ID:
            await message.reply_text("❌ CHANNEL_ID не задан в конфиге.")
            return ConversationHandler.END
        
        # Сохраняем подпись если есть
        caption = message.caption if message.caption else None
        
        # Отправляем в зависимости от типа
        if message.text:
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=message.text
            )
            logger.info(f"📤 Владелец отправил текст в канал: {message.text[:50]}...")
            
        elif message.photo:
            # Берём самое качественное фото
            photo = message.photo[-1]
            await bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=photo.file_id,
                caption=caption
            )
            logger.info(f"📤 Владелец отправил фото в канал")
            
        elif message.video:
            await bot.send_video(
                chat_id=CHANNEL_ID,
                video=message.video.file_id,
                caption=caption
            )
            logger.info(f"📤 Владелец отправил видео в канал")
            
        elif message.animation:
            await bot.send_animation(
                chat_id=CHANNEL_ID,
                animation=message.animation.file_id,
                caption=caption
            )
            logger.info(f"📤 Владелец отправил GIF в канал")
            
        elif message.document:
            await bot.send_document(
                chat_id=CHANNEL_ID,
                document=message.document.file_id,
                caption=caption
            )
            logger.info(f"📤 Владелец отправил документ в канал")
        
        await message.reply_text(
            "✅ *Контент успешно отправлен в канал!*",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки в канал: {e}")
        await message.reply_text(
            f"❌ Ошибка отправки: {e}"
        )
    
    return ConversationHandler.END


async def cancel_resend(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена отправки."""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ У вас нет прав.")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "❌ Отправка в канал отменена.",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


def get_resend_conversation_handler():
    """Возвращает ConversationHandler для команды /resend."""
    return ConversationHandler(
        entry_points=[CommandHandler("resend", resend_command)],
        states={
            AWAITING_CONTENT: [
                MessageHandler(
                    filters.TEXT | filters.PHOTO | filters.VIDEO | filters.ANIMATION | filters.Document.ALL,
                    handle_content
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_resend)],
        name="resend_conversation",
        persistent=False,
    )
