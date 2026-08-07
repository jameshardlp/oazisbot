"""Чтение и запись JSON-состояния бота.

Разделяемые коллекции `users`, `history`, `schedule_data` загружаются один раз
при импорте и правятся ТОЛЬКО на месте (append/remove/[key] = value).
Присваивание имени целиком разорвёт связь с другими модулями.
"""
import json
import logging
from datetime import datetime

from config import USERS_FILE, HISTORY_FILE, SCHEDULE_FILE, USAGE_FILE

logger = logging.getLogger(__name__)

def load_users():
    try:
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_users(users_list):
    try:
        with open(USERS_FILE, "w") as f:
            json.dump(users_list, f)
    except Exception as e:
        logger.error(f"Ошибка сохранения пользователей: {e}")

def load_history():
    try:
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_history(history_list):
    try:
        if len(history_list) > 100:
            history_list = history_list[-100:]
        with open(HISTORY_FILE, "w") as f:
            json.dump(history_list, f)
    except Exception as e:
        logger.error(f"Ошибка сохранения истории: {e}")

def load_schedule():
    try:
        with open(SCHEDULE_FILE, "r") as f:
            data = json.load(f)
            if not data or not data.get("times"):
                return {"times": ["12:00", "21:00"]}
            return data
    except:
        return {"times": ["12:00", "21:00"]}

def save_schedule(schedule_data):
    try:
        with open(SCHEDULE_FILE, "w") as f:
            json.dump(schedule_data, f)
        return True
    except:
        return False

def load_usage() -> dict:
    try:
        with open(USAGE_FILE, "r") as f:
            data = json.load(f)
            current_date = datetime.now().strftime("%Y-%m-%d")
            for user_id in list(data.keys()):
                if data[user_id].get("date") != current_date:
                    del data[user_id]
            return data
    except:
        return {}

def save_usage(usage_data: dict):
    try:
        with open(USAGE_FILE, "w") as f:
            json.dump(usage_data, f)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения статистики: {e}")
        return False


# Загружается один раз при импорте. Править только на месте — см. docstring модуля.
users = load_users()
history = load_history()
schedule_data = load_schedule()
