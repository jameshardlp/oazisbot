"""Чтение и запись JSON-состояния бота.

Разделяемые коллекции `users`, `history`, `schedule_data` загружаются один раз
при импорте и правятся ТОЛЬКО на месте (append/remove/[key] = value).
Присваивание имени целиком разорвёт связь с другими модулями.
"""
import json
import logging
from datetime import datetime
from typing import List, Dict, Any

from config import USERS_FILE, HISTORY_FILE, SCHEDULE_FILE, USAGE_FILE

logger = logging.getLogger(__name__)

def load_users() -> List[int]:
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_users(users_list: List[int]) -> None:
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users_list, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения пользователей: {e}")

def load_history() -> List[str]:
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_history(history_list: List[str]) -> None:
    try:
        if len(history_list) > 100:
            history_list = history_list[-100:]
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history_list, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения истории: {e}")

def load_schedule() -> Dict[str, Any]:
    try:
        with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not data or not data.get("times"):
                return {"times": ["12:00", "21:00"]}
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {"times": ["12:00", "21:00"]}

def save_schedule(schedule_data: Dict[str, Any]) -> bool:
    try:
        with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
            json.dump(schedule_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения расписания: {e}")
        return False

def load_usage() -> Dict[str, Any]:
    try:
        with open(USAGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            current_date = datetime.now().strftime("%Y-%m-%d")
            for user_id in list(data.keys()):
                if data[user_id].get("date") != current_date:
                    del data[user_id]
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_usage(usage_data: Dict[str, Any]) -> bool:
    try:
        with open(USAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(usage_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения статистики: {e}")
        return False


# Загружается один раз при импорте. Править только на месте — см. docstring модуля.
users: List[int] = load_users()
history: List[str] = load_history()
schedule_data: Dict[str, Any] = load_schedule()
