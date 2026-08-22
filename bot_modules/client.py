"""Клиент для работы с Telegram."""
import logging
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from telegram import Update
from config import BOT_TOKEN

logger = logging.getLogger(__name__)

# Создаём приложение
application = Application.builder().token(BOT_TOKEN).build()

# Dispatcher
dp = application.dispatcher

# Bot instance
bot = application.bot

logger.info("✅ Бот успешно инициализирован")