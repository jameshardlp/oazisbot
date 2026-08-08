"""Планировщик публикаций по расписанию."""
import asyncio
import logging
import random
import time
from datetime import datetime

from config import MIN_POST_INTERVAL, SEND_DELAY
from storage import schedule_data
from telegram.posting import create_post_with_photo, send_to_all_users

logger = logging.getLogger(__name__)

# Защита от параллельных публикаций. Читаются и пишутся только в scheduler().
is_sending = False
last_post_time = time.time()

async def scheduler():
    global is_sending, last_post_time
    await asyncio.sleep(10)
    logger.info("🔄 Планировщик запущен")
    logger.info(f"📅 Расписание: {schedule_data.get('times', ['12:00', '21:00'])}")
    logger.info(f"⏱️ Минимальный интервал: {MIN_POST_INTERVAL//3600} часов")
    logger.info(f"⏱️ Задержка между сообщениями: {SEND_DELAY} секунд")
    
    # Уже отработанные слоты вида "2026-08-07 12:00". Сравнение по точной минуте
    # проскакивало слот при дрейфе цикла: sleep(60) плюс время итерации могли
    # перепрыгнуть с 11:59 сразу на 12:01.
    fired_slots = set()

    while True:
        try:
            now = datetime.now()
            schedule_times = schedule_data.get("times", ["12:00", "21:00"])

            due = None
            for slot in schedule_times:
                try:
                    hh, mm = (int(p) for p in slot.split(":"))
                except ValueError:
                    logger.warning(f"⚠️ Некорректный слот расписания: {slot}")
                    continue
                slot_dt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
                key = f"{now:%Y-%m-%d} {slot}"
                if key not in fired_slots and now >= slot_dt and (now - slot_dt).total_seconds() < 3600:
                    due = (slot, key)
                    break

            if due and not is_sending and time.time() - last_post_time >= MIN_POST_INTERVAL:
                slot, key = due
                fired_slots.add(key)
                is_sending = True
                try:
                    random_delay = random.randint(0, 2700)
                    logger.info(f"🎲 Случайная задержка {random_delay//60} минут")
                    await asyncio.sleep(random_delay)

                    if random.random() < 0.05:
                        logger.info("🎲 Случайный пропуск отправки (5%)")
                    else:
                        logger.info(f"📢 Отправка по расписанию {slot}")
                        await send_to_all_users()
                        logger.info(f"✅ Пост отправлен в {datetime.now():%H:%M}")
                    last_post_time = time.time()
                except Exception as e:
                    logger.error(f"❌ Ошибка отправки: {e}")
                finally:
                    is_sending = False

            # Слоты старше суток не нужны
            today = f"{datetime.now():%Y-%m-%d}"
            fired_slots = {k for k in fired_slots if k.startswith(today)}

            await asyncio.sleep(60)

        except Exception as e:
            logger.error(f"❌ Ошибка в планировщике: {e}")
            await asyncio.sleep(60)
