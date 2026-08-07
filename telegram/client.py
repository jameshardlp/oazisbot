"""Экземпляры Bot и Dispatcher.

Отдельный модуль, чтобы хендлеры могли импортировать `dp` для декораторов,
не создавая циклический импорт через точку входа.
"""
import logging
import sys

from aiogram import Bot, Dispatcher

from ..config import BOT_TOKEN
from .rate_limit import RateLimitMiddleware

logger = logging.getLogger(__name__)

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не задан в переменных окружения")
    sys.exit(1)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
dp.message.middleware(RateLimitMiddleware())
