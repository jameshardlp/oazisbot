"""Команды /start, /photo, /post, /stop, /status."""
import asyncio
import logging

from aiogram.filters import Command
from aiogram.types import Message

from ...config import OWNER_ID, CHANNEL_ID, UNLIMITED
from ...storage import load_users, save_users, load_schedule, users, history
from ...payments.orders import broadcast_prices
from ..client import dp
from ..posting import create_post_with_photo, send_to_all_users, get_channel_id
from ..quota import can_use_photo, increment_photo_usage, format_limit

logger = logging.getLogger(__name__)

@dp.message(Command("start"))
async def start(msg: Message):
    try:
        chat_id = msg.chat.id
        
        if chat_id not in users:
            users.append(chat_id)
            save_users(users)
            logger.info(f"👤 Добавлен пользователь: {chat_id}")
        
        current_schedule = load_schedule()
        times = ", ".join(current_schedule.get("times", ["12:00", "21:00"]))
        stars_price = broadcast_prices.get("stars", 100)
        rub_price = broadcast_prices.get("rub", 100)
        
        channel_status = "❌ не найден"
        channel_id = CHANNEL_ID or await get_channel_id()
        if channel_id:
            channel_status = f"✅ {channel_id}"
        
        await msg.answer(
            f"✅ Бот активирован!\n\n"
            f"📸 Посты про стримеров и Азию\n"
            f"⏰ Расписание: {times}\n"
            f"📢 Канал: {channel_status}\n\n"
            f"🔄 /photo - получить пост сейчас (до 10 раз в день)\n"
            f"⏰ /schedule - изменить расписание (только для владельца)\n"
            f"📢 /broadcast - отправить сообщение всем (⭐ {stars_price} звёзд или 💳 {rub_price} RUB)\n"
            f"🛑 /stop - отписаться\n"
            f"📊 /status - статус бота"
        )
        
    except Exception as e:
        logger.error(f"Ошибка в команде start: {e}")

@dp.message(Command("photo"))
async def photo_command(message: Message):
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        if chat_id not in users:
            await message.answer("⚠️ Бот не активирован. Напишите /start")
            return
        
        can_use, used_count, limit = can_use_photo(user_id)
        
        if not can_use:
            await message.answer(
                f"⛔ Вы исчерпали лимит на сегодня ({limit} запросов).\n"
                f"🔄 Лимит обновится завтра."
            )
            return
        
        ok = await create_post_with_photo(chat_id, user_id, skip_moderation=True)

        if not ok:
            await message.answer("❌ Не удалось сгенерировать пост. Попробуйте ещё раз.")
            return

        # Лимит списывается только за реально отправленный пост: раньше счётчик
        # рос и при провале генерации, а пользователь всё равно видел «отправлено».
        new_count, limit = increment_photo_usage(user_id)
        remaining = limit - new_count

        await message.answer(
            f"✅ Пост отправлен!\n"
            f"📊 Осталось запросов на сегодня: {format_limit(remaining)} из {format_limit(limit)}"
        )
    except Exception as e:
        logger.error(f"Ошибка в команде photo: {e}")

@dp.message(Command("post"))
async def post_command(message: Message):
    try:
        if message.from_user.id != OWNER_ID:
            await message.answer("⛔ Доступ запрещён")
            return
        
        channel_id = CHANNEL_ID or await get_channel_id()
        if channel_id:
            await create_post_with_photo(str(channel_id), message.from_user.id, skip_moderation=True)
            await message.answer("✅ Пост создан для канала!")
        else:
            await message.answer("⚠️ Канал не найден. Укажите CHANNEL_ID в переменных окружения.")
        
        await create_post_with_photo(str(message.chat.id), message.from_user.id, skip_moderation=True)
        await message.answer("✅ Пост создан в ЛС!")
    except Exception as e:
        logger.error(f"Ошибка в команде post: {e}")
        await message.answer("❌ Произошла ошибка")

@dp.message(Command("stop"))
async def stop(msg: Message):
    try:
        chat_id = msg.chat.id
        if chat_id in users:
            users.remove(chat_id)
            save_users(users)
            await msg.answer("🛑 Вы отписаны от рассылки")
        else:
            await msg.answer("ℹ️ Вы и так не подписаны")
    except Exception as e:
        logger.error(f"Ошибка в команде stop: {e}")

@dp.message(Command("status"))
async def status(msg: Message):
    try:
        users_list = load_users()
        current_schedule = load_schedule()
        times = ", ".join(current_schedule.get("times", ["12:00", "21:00"]))
        channel_id = CHANNEL_ID or await get_channel_id()
        
        await msg.answer(
            f"📊 Статус бота:\n"
            f"• Подписчиков: {len(users_list)}\n"
            f"• Фото в истории: {len(history)}\n"
            f"• Расписание: {times}\n"
            f"• Канал: {'✅ ' + channel_id if channel_id else '❌ не найден'}"
        )
    except Exception as e:
        logger.error(f"Ошибка в команде status: {e}")
