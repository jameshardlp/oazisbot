"""Базовые обработчики команд."""
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

logger = logging.getLogger(__name__)

OWNER_COMMANDS = (
    "Только для владельца:\n"
    "/resend - отправить свой контент в канал\n"
    "/postnow - выложить мем из каналов-источников прямо сейчас\n"
    "/mode - переключить режим: стримеры или мемы\n"
    "/interval - интервал между автопостами\n"
    "/sources - список каналов, откуда берутся мемы\n"
    "/schedule - текущие настройки публикации\n"
    "/stats - статистика"
)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start."""
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n"
        "Я бот для автоматической публикации постов и мемов.\n\n"
        "Доступные команды:\n"
        "/start - показать это сообщение\n"
        "/help - помощь\n"
        "/photo - случайное фото стримера\n\n"
        f"{OWNER_COMMANDS}"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help."""
    await update.message.reply_text(
        "🤖 Помощь\n\n"
        "Бот автоматически публикует в канал один вид контента — тот, что выбран\n"
        "командой /mode:\n"
        "• streamers - посты про стримеров (текст + ссылка на клип)\n"
        "• memes - мемы из каналов-источников\n\n"
        "Доступные команды:\n"
        "/start - приветствие\n"
        "/help - эта справка\n"
        "/photo - случайное фото стримера\n\n"
        f"{OWNER_COMMANDS}"
    )


def register_basic_handlers(app):
    """Регистрирует базовые обработчики."""
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
