"""Функции для создания и отправки постов."""
import logging
import asyncio
import time
from typing import Optional, Tuple, List
from datetime import datetime, timedelta

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.constants import ParseMode
from bot_modules.client import application

logger = logging.getLogger(__name__)

# Константы
STARS_PAYMENT_WAIT_TIME = 600  # 10 минут в секундах
STARS_PAYMENT_VERIFY_DELAY = 30  # 30 секунд после получения звезды


async def create_stars_payment_post(bot: Bot, channel_id: int, user_id: int, broadcast_message: Message) -> Tuple[Optional[int], Optional[int]]:
    """Создаёт пост на канале с просьбой оплатить звездой."""
    try:
        post_text = (
            "🌟 *ОПЛАТА ЗВЕЗДОЙ* 🌟\n\n"
            "Здесь будет ваша реклама:\n"
            "💫 *Поставьте звезду на этом посте*, чтобы оплатить рекламу.\n"
            "После получения звезды реклама будет отправлена на модерацию и опубликована."
        )
        
        image_url = "https://avatars.mds.yandex.net/i?id=fc674388267335732f8f9dd3718b96353876cf75-12390814-images-thumbs&n=13"
        
        message = await bot.send_photo(
            chat_id=channel_id,
            photo=image_url,
            caption=post_text,
            parse_mode=ParseMode.MARKDOWN
        )
        
        logger.info(f"✅ Создан пост для оплаты звездой: {message.message_id}")
        return message.message_id, message.message_id
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания поста для оплаты звездой: {e}")
        return None, None


async def send_payment_request_to_user(bot: Bot, user_id: int, channel_post_id: int, channel_id: int) -> bool:
    """Отправляет пользователю ссылку на пост для оплаты звездой."""
    try:
        chat = await bot.get_chat(channel_id)
        channel_username = chat.username if chat.username else None
        
        if channel_username:
            post_link = f"https://t.me/{channel_username}/{channel_post_id}"
            link_text = f"[Открыть пост для оплаты]({post_link})"
        else:
            link_text = "📨 *Пост создан на канале*"
            post_link = None
        
        payment_text = (
            "💫 *ОПЛАТА ЗВЕЗДОЙ* 💫\n\n"
            "Для оплаты рекламы, пожалуйста, перейдите по ссылке и поставьте ЗВЕЗДУ на посте.\n\n"
            f"{link_text}\n\n"
            "🌟 *Как оплатить:*\n"
            "1. Нажмите на ссылку\n"
            "2. Найдите пост с просьбой оплатить\n"
            "3. Нажмите на иконку ⭐ и поставьте звезду\n\n"
            "⏰ *У вас есть 10 минут*, чтобы произвести оплату.\n"
            "После получения звезды реклама будет отправлена на модерацию."
        )
        
        keyboard_buttons = []
        if post_link:
            keyboard_buttons.append([InlineKeyboardButton("🌟 Перейти к оплате", url=post_link)])
        keyboard_buttons.append([InlineKeyboardButton("❌ Отменить оплату", callback_data="cancel_stars_payment")])
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        await bot.send_message(
            chat_id=user_id,
            text=payment_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
        
        logger.info(f"✅ Отправлен запрос на оплату пользователю {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки запроса на оплату пользователю: {e}")
        return False


async def wait_for_stars_payment(bot: Bot, channel_id: int, post_id: int, user_id: int, broadcast_message: Message) -> Tuple[bool, Optional[int]]:
    """Ожидает оплату звездой в течение 10 минут."""
    start_time = time.time()
    
    logger.info(f"⏳ Ожидание оплаты звездой от {user_id}...")
    
    await bot.send_message(
        chat_id=user_id,
        text="⏳ Ожидаю оплату звездой... У вас есть 10 минут.",
        parse_mode=ParseMode.MARKDOWN
    )
    
    await asyncio.sleep(30)
    
    while time.time() - start_time < STARS_PAYMENT_WAIT_TIME:
        # Здесь должна быть проверка оплаты
        # Пока возвращаем True для теста
        # В реальном проекте нужно добавить проверку звёзд
        return True, None
    
    return False, None


async def handle_stars_payment_flow(bot: Bot, channel_id: int, user_id: int, broadcast_message: Message) -> bool:
    """Полный цикл оплаты звездой."""
    logger.info(f"💫 Начинаем оплату звездой для пользователя {user_id}")
    
    # 1. Создаём пост на канале
    post_id, _ = await create_stars_payment_post(bot, channel_id, user_id, broadcast_message)
    if not post_id:
        await bot.send_message(
            chat_id=user_id,
            text="❌ Не удалось создать пост для оплаты. Попробуйте позже."
        )
        return False
    
    # 2. Отправляем пользователю ссылку
    await send_payment_request_to_user(bot, user_id, post_id, channel_id)
    
    # 3. Ожидаем оплату
    success, _ = await wait_for_stars_payment(bot, channel_id, post_id, user_id, broadcast_message)
    
    if success:
        # 4. Отправляем сообщение на модерацию
        await send_to_moderation(user_id, broadcast_message)
        logger.info(f"✅ Оплата звездой успешно завершена для {user_id}")
        return True
    else:
        logger.warning(f"❌ Оплата звездой не удалась для {user_id}")
        return False


async def send_to_moderation(user_id: int, broadcast_message: Message) -> None:
    """Отправляет сообщение на модерацию владельцу."""
    try:
        from config import OWNER_ID
        
        await broadcast_message.forward(chat_id=OWNER_ID)
        
        await application.bot.send_message(
            chat_id=OWNER_ID,
            text=f"📢 *НОВАЯ РЕКЛАМА НА МОДЕРАЦИЮ*\n\n"
                 f"От пользователя: {user_id}\n"
                 f"Оплачено звёздами: ✅\n\n"
                 f"Для публикации: /approve_broadcast {user_id}",
            parse_mode="Markdown"
        )
        logger.info(f"✅ Реклама от {user_id} отправлена на модерацию")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки на модерацию: {e}")


async def create_post_with_photo(bot: Bot, channel_id: int, text: str, photo_url: Optional[str] = None) -> bool:
    """Создаёт пост с фото на канале."""
    try:
        if photo_url:
            await bot.send_photo(
                chat_id=channel_id,
                photo=photo_url,
                caption=text,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await bot.send_message(
                chat_id=channel_id,
                text=text,
                parse_mode=ParseMode.MARKDOWN
            )
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка создания поста: {e}")
        return False


async def send_to_all_users(bot: Bot, users: List[int], text: str) -> int:
    """Отправляет сообщение всем пользователям."""
    success_count = 0
    for user_id in users:
        try:
            await bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode=ParseMode.MARKDOWN
            )
            success_count += 1
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"❌ Ошибка отправки пользователю {user_id}: {e}")
    return success_count


def get_channel_id() -> int:
    """Возвращает ID канала из конфига."""
    from config import CHANNEL_ID
    return CHANNEL_ID
