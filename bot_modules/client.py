"""Клиент для работы с Telegram."""
import logging
from telegram.ext import Application
from config import BOT_TOKEN

logger = logging.getLogger(__name__)

# Создаём приложение
application = Application.builder().token(BOT_TOKEN).build()

# Bot instance
bot = application.bot

# Для обратной совместимости — dp указывает на application
dp = application

logger.info("✅ Бот успешно инициализирован")
