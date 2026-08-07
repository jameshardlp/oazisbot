"""Лимит частоты сообщений. Оплаченные рассылки не отбрасываются."""
import logging
import time
from collections import defaultdict
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message

logger = logging.getLogger(__name__)

class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, seconds: int = 3):
        super().__init__()
        self.seconds = seconds
        self.user_last_message = defaultdict(float)
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id
        current_time = time.time()

        # Сообщение об успешной оплате приходит от Telegram, а не от человека.
        # Раньше оно попадало под общий лимит и могло быть отброшено — вместе
        # с оплаченной рассылкой.
        if getattr(event, "successful_payment", None) is not None:
            return await handler(event, data)

        last_time = self.user_last_message.get(user_id, 0)

        if current_time - last_time < self.seconds:
            logger.info(f"⏭️ Игнорируем частый запрос от {user_id} ({(current_time - last_time):.1f} сек)")
            return

        self.user_last_message[user_id] = current_time
        return await handler(event, data)
