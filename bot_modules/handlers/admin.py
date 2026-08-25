"""Административные команды.

/start живёт в basic.py: register_admin_handlers вызывается первым, и дубль
CommandHandler("start") здесь перехватывал команду, потому что внутри группы
срабатывает только первый совпавший хендлер.
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from config import OWNER_ID, CHANNEL_ID

logger = logging.getLogger(__name__)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /stats (только для владельца)."""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ У вас нет прав.")
        return
    
    await update.message.reply_text(
        "📊 *Статистика бота*\n\n"
        f"Канал: {CHANNEL_ID}\n"
        f"Владелец: {OWNER_ID}",
        parse_mode="Markdown"
    )


async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /schedule (только для владельца)."""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ У вас нет прав.")
        return
    
    await update.message.reply_text(
        "📅 *Управление расписанием*\n\n"
        "Функция в разработке.",
        parse_mode="Markdown"
    )


def register_admin_handlers(app):
    """Регистрирует административные команды."""
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("schedule", schedule_command))
