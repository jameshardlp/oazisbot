"""Экземпляры Bot и Dispatcher.

Отдельный модуль, чтобы хендлеры могли импортировать `dp` для декораторов,
не создавая циклический импорт через точку входа.
"""
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# Абсолютный импорт вместо относительного
from config import BOT_TOKEN
from .rate_limit import RateLimitMiddleware

logger = logging.getLogger(__name__)

# Проверка токена
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не задан в переменных окружения")
    sys.exit(1)

# Создание бота с настройками
try:
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,  # или ParseMode.MARKDOWN
        )
    )
    logger.info("✅ Бот успешно инициализирован")
except Exception as e:
    logger.error(f"❌ Ошибка при создании бота: {e}")
    sys.exit(1)

# Создание диспетчера
dp = Dispatcher()

# Регистрация middleware (правильный синтаксис для aiogram 3.x)
dp.message.middleware(RateLimitMiddleware())
# Если есть callback middleware:
# dp.callback_query.middleware(RateLimitMiddleware())
