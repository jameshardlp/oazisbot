"""Административные команды.

/start живёт в basic.py: register_admin_handlers вызывается первым, и дубль
CommandHandler("start") здесь перехватывал команду, потому что внутри группы
срабатывает только первый совпавший хендлер.
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

import settings
from config import OWNER_ID, CHANNEL_ID, CONTENT_MODE, is_admin

logger = logging.getLogger(__name__)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /stats (только для владельца)."""
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав.")
        return

    await update.message.reply_text(
        "📊 *Статистика бота*\n\n"
        f"Канал: {CHANNEL_ID}\n"
        f"Владелец: {OWNER_ID}",
        parse_mode="Markdown"
    )


async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /schedule — текущие настройки публикации.

    Без parse_mode: в списке каналов есть имена с подчёркиваниями, Markdown
    их бы искалечил.
    """
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав.")
        return

    if CONTENT_MODE == "streamers":
        mode_line = "streamers — посты про стримеров (текст + ссылка на клип)"
    else:
        mode_line = "memes — мемы из каналов-источников"

    channels = settings.get_meme_channels()
    channels_line = ", ".join(channels) if channels else "список пуст"

    await update.message.reply_text(
        "📅 Настройки публикации\n\n"
        f"Режим: {mode_line}\n"
        f"Канал: {CHANNEL_ID or 'не задан'}\n"
        f"Интервал: {settings.describe_interval()}\n"
        f"Каналы-источники ({len(channels)}): {channels_line}\n\n"
        "Изменить: /interval — интервал, /sources — каналы, "
        "/postnow — выложить мем сейчас.\n"
        "Режим задаётся переменной окружения CONTENT_MODE и требует перезапуска."
    )


def register_admin_handlers(app):
    """Регистрирует административные команды."""
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("schedule", schedule_command))
