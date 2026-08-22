"""Команды владельца: /schedule, /price, /check_channel."""
import logging

from aiogram.filters import Command
from aiogram.types import Message

from config import OWNER_ID, STARS_CHANNEL_ID
from storage import load_schedule, save_schedule, schedule_data
from payments.orders import broadcast_prices, save_broadcast_price
from telegram.client import bot, dp

logger = logging.getLogger(__name__)

@dp.message(Command("schedule"))
async def schedule(msg: Message):
    try:
        if msg.from_user.id != OWNER_ID:
            await msg.answer("⛔ Доступ запрещён")
            return
        
        args = msg.text.replace("/schedule", "").strip()
        if not args:
            current_schedule = load_schedule()
            times = ", ".join(current_schedule.get("times", ["12:00", "21:00"]))
            await msg.answer(f"📅 Текущее расписание: {times}")
            return
        
        new_times = []
        for time_str in args.split(','):
            time_str = time_str.strip()
            try:
                hour, minute = map(int, time_str.split(':'))
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    new_times.append(f"{hour:02d}:{minute:02d}")
            except ValueError:
                continue
        
        if new_times:
            schedule_data["times"] = new_times
            save_schedule(schedule_data)
            await msg.answer(f"✅ Расписание обновлено: {', '.join(new_times)}")
        else:
            await msg.answer("❌ Неверный формат. Используйте: /schedule 12:00,21:00")
    except Exception as e:
        logger.error(f"Ошибка в команде schedule: {e}")
        await msg.answer("❌ Произошла ошибка")

@dp.message(Command("price"))
async def set_price(message: Message):
    try:
        if message.from_user.id != OWNER_ID:
            await message.answer("⛔ Доступ запрещён")
            return
        
        args = message.text.replace("/price", "").strip()
        if not args:
            stars_price = broadcast_prices.get("stars", 100)
            rub_price = broadcast_prices.get("rub", 100)
            await message.answer(
                f"💰 Текущие цены:\n"
                f"⭐ Звёзды: {stars_price}\n"
                f"💳 Рубли: {rub_price} RUB"
            )
            return
        
        parts = args.split()
        if len(parts) != 2:
            await message.answer("❌ Использование: /price stars 10 или /price rub 100")
            return
        
        currency, value = parts[0].lower(), parts[1]
        try:
            price = int(value)
            if price < 1:
                await message.answer("❌ Цена должна быть > 0")
                return
            
            if currency == "stars":
                broadcast_prices["stars"] = price
                save_broadcast_price(broadcast_prices)
                await message.answer(f"✅ Цена в звёздах: {price} ⭐")
            elif currency == "rub":
                broadcast_prices["rub"] = price
                save_broadcast_price(broadcast_prices)
                await message.answer(f"✅ Цена в рублях: {price} RUB")
            else:
                await message.answer("❌ Укажите stars или rub")
        except ValueError:
            await message.answer("❌ Введите число")
    except Exception as e:
        logger.error(f"Ошибка в команде price: {e}")
        await message.answer("❌ Произошла ошибка")

@dp.message(Command("check_channel"))
async def check_channel(message: Message):
    try:
        if message.from_user.id != OWNER_ID:
            await message.answer("⛔ Доступ запрещён")
            return
        try:
            chat_member = await bot.get_chat_member(STARS_CHANNEL_ID, bot.id)
            status_text = f"📊 Статус бота в канале {STARS_CHANNEL_ID}:\n"
            status_text += f"• Статус: {chat_member.status}\n"
            status_text += f"• Может отправлять: {chat_member.can_send_messages}\n"
            status_text += f"• Может управлять: {chat_member.can_manage_chat}\n"
            status_text += f"• Может публиковать: {chat_member.can_post_messages}\n"
            status_text += f"• Может управлять видеочатами: {chat_member.can_manage_video_chats}\n"
            await message.answer(status_text)
        except Exception as e:
            await message.answer(f"❌ Ошибка: {e}\n\nУбедитесь, что бот добавлен в канал {STARS_CHANNEL_ID} как администратор.")
    except Exception as e:
        logger.error(f"Ошибка проверки канала: {e}")
        await message.answer("❌ Произошла ошибка")
