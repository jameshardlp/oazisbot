"""Клиент для работы с Telegram."""
import logging
from telegram.ext import Application
from config import BOT_TOKEN

logger = logging.getLogger(__name__)

# Создаём приложение
application = Application.builder().token(BOT_TOKEN).build()

# Для обратной совместимости с вашим кодом
# В python-telegram-bot v20+ Application сам является Dispatcher
dp = application

# Bot instance
bot = application.bot

logger.info("✅ Бот успешно инициализирован")
