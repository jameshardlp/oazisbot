"""Базовые обработчики команд."""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start."""
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n"
        "Я бот для автоматической публикации постов и мемов.\n\n"
        "Доступные команды:\n"
        "/start - показать это сообщение\n"
        "/help - помощь\n"
        "/resend - отправить контент в канал (только для владельца)",
        parse_mode="Markdown"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help."""
    await update.message.reply_text(
        "🤖 *Помощь*\n\n"
        "Бот автоматически публикует:\n"
        "• Посты про стримеров (текст + ссылки на YouTube)\n"
        "• Мемы из каналов-источников\n\n"
        "Доступные команды:\n"
        "/start - приветствие\n"
        "/help - эта справка\n"
        "/resend - отправить контент в канал (только для владельца)",
        parse_mode="Markdown"
    )


def register_basic_handlers(app):
    """Регистрирует базовые обработчики."""
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
