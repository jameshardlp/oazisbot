"""Клиент для работы с Telegram."""
import logging
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from telegram import Update
from config import BOT_TOKEN

logger = logging.getLogger(__name__)

# Создаём приложение
application = Application.builder().token(BOT_TOKEN).build()

# В новой версии (v20+) dispatcher - это сам application
# dp используется как алиас для application
dp = application

# Bot instance
bot = application.bot

logger.info("✅ Бот успешно инициализирован")
