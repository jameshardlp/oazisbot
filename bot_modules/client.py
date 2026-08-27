"""Клиент для работы с Telegram."""
import logging
from telegram.ext import Application
from config import BOT_TOKEN

logger = logging.getLogger(__name__)

# Создаём приложение.
# Таймауты подняты из-за мемов: дефолт python-telegram-bot на запись — 20 с, а
# видео из t.me весит десятки мегабайт, и аплоад не успевал уложиться. Отказ по
# таймауту выглядел как «Telegram не принимает видео».
application = (
    Application.builder()
    .token(BOT_TOKEN)
    .connect_timeout(30)
    .read_timeout(60)
    .write_timeout(180)
    .media_write_timeout(300)
    .build()
)

# Bot instance
bot = application.bot

logger.info("✅ Бот успешно инициализирован")
