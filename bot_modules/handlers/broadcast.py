"""Обработчик команды /broadcast для создания рекламных постов."""
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters

from bot_modules.posting import handle_stars_payment_flow
from config import CHANNEL_ID, OWNER_ID
from bot_modules.client import dp

logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
AWAITING_CONTENT = 1


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик команды /broadcast.
    Запускает процесс создания рекламы — запрашивает контент у пользователя.
    """
    user_id = update.effective_user.id
    
    # Проверяем, что пользователь — владелец
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ У вас нет прав на использование этой команды.")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "📝 *Отправьте ваше рекламное сообщение*\n\n"
        "Это может быть:\n"
        "• Текст\n"
        "• Фото с подписью\n"
        "• Видео с подписью\n"
        "• Документ (файл) с подписью\n\n"
        "После отправки выберите способ оплаты.\n\n"
        "❌ Для отмены отправьте /cancel",
        parse_mode="Markdown"
    )
    
    return AWAITING_CONTENT


async def handle_broadcast_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик получения контента от пользователя.
    Сохраняет сообщение и предлагает выбор оплаты.
    """
    user_id = update.effective_user.id
    message = update.message
    
    # Проверяем права
    if user_id != OWNER_ID:
        await message.reply_text("❌ У вас нет прав.")
        return ConversationHandler.END
    
    # Проверяем, что пользователь что-то отправил
    if not message.text and not message.photo and not message.video and not message.document and not message.animation:
        await message.reply_text(
            "⚠️ Пожалуйста, отправьте текст, фото, видео или файл."
        )
        return AWAITING_CONTENT
    
    # Сохраняем ВСЁ сообщение (вместе с медиа)
    context.user_data['broadcast_message'] = message
    
    # Показываем выбор способа оплаты
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💎 Оплатить звёздами", callback_data="pay_with_stars"),
            InlineKeyboardButton("💳 Оплатить картой", callback_data="pay_with_card"),
        ],
        [InlineKeyboardButton("❌ Отменить", callback_data="cancel_broadcast")]
    ])
    
    await message.reply_text(
        "📢 *Ваше сообщение получено!*\n\n"
        "Выберите способ оплаты:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    
    return ConversationHandler.END


async def broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик кнопок для оплаты рекламы.
    """
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    broadcast_message = context.user_data.get('broadcast_message')
    
    # Проверяем права
    if user_id != OWNER_ID:
        await query.edit_message_text("❌ У вас нет прав.")
        return
    
    if data == "cancel_broadcast":
        await query.edit_message_text("❌ Реклама отменена.")
        context.user_data.pop('broadcast_message', None)
        return
    
    if not broadcast_message:
        await query.edit_message_text(
            "❌ Ошибка: сообщение не найдено. Попробуйте начать заново: /broadcast"
        )
        return
    
    if data == "pay_with_stars":
        await query.edit_message_text("💫 *Запуск оплаты звёздами...*\n\nОжидайте...", parse_mode="Markdown")
        
        try:
            # Запускаем процесс оплаты звёздами
            success = await handle_stars_payment_flow(
                bot=context.bot,
                channel_id=CHANNEL_ID,
                user_id=user_id,
                broadcast_message=broadcast_message
            )
            
            if success:
                # Уведомляем пользователя
                await query.edit_message_text(
                    "✅ *Оплата прошла успешно!*\n\n"
                    "Ваше сообщение отправлено на модерацию и будет опубликовано после проверки.",
                    parse_mode="Markdown"
                )
                
                # Очищаем сохранённое сообщение
                context.user_data.pop('broadcast_message', None)
                
            else:
                await query.edit_message_text(
                    "❌ *Оплата не удалась.*\n\n"
                    "Попробуйте снова или выберите другой способ оплаты: /broadcast",
                    parse_mode="Markdown"
                )
                
        except Exception as e:
            logger.error(f"❌ Ошибка при оплате звёздами: {e}")
            await query.edit_message_text(
                "❌ Произошла ошибка при оплате. Попробуйте позже: /broadcast"
            )
    
    elif data == "pay_with_card":
        # Обработка оплаты картой (существующая логика)
        await query.edit_message_text(
            "💳 *Оплата картой*\n\n"
            "Этот способ оплаты временно недоступен. Пожалуйста, выберите оплату звёздами.",
            parse_mode="Markdown"
        )


async def cancel_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена создания рекламы."""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ У вас нет прав.")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "❌ Создание рекламы отменено.",
        parse_mode="Markdown"
    )
    context.user_data.pop('broadcast_message', None)
    return ConversationHandler.END


def get_broadcast_conversation_handler():
    """Возвращает ConversationHandler для обработки /broadcast."""
    return ConversationHandler(
        entry_points=[CommandHandler("broadcast", broadcast_command)],
        states={
            AWAITING_CONTENT: [
                MessageHandler(
                    filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL | filters.ANIMATION,
                    handle_broadcast_content
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_broadcast)],
        name="broadcast_conversation",
        persistent=False,
    )


# Регистрируем обработчик для callback'ов (кнопок)
dp.add_handler(CallbackQueryHandler(broadcast_callback, pattern="^(pay_with_stars|pay_with_card|cancel_broadcast|cancel_stars_payment)$"))
