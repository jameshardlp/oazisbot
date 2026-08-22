"""Суточный лимит команды /photo."""
from datetime import datetime
from typing import Tuple

from config import DAILY_PHOTO_LIMIT, UNLIMITED, OWNER_ID
from storage import load_usage, save_usage

def format_limit(value) -> str:
    """Показывает безлимит как ∞ вместо 'inf' в тексте для пользователя."""
    return "∞" if value == UNLIMITED else str(value)

def can_use_photo(user_id: int) -> Tuple[bool, int, int]:
    if user_id == OWNER_ID:
        return True, 0, UNLIMITED

    usage_data = load_usage()
    current_date = datetime.now().strftime("%Y-%m-%d")
    user_key = str(user_id)
    limit = DAILY_PHOTO_LIMIT

    if user_key not in usage_data:
        return True, 0, limit
    
    user_usage = usage_data.get(user_key, {})
    last_date = user_usage.get("date")
    count = user_usage.get("count", 0)
    
    if last_date != current_date:
        return True, 0, limit
    
    if count >= limit:
        return False, count, limit
    
    return True, count, limit

def increment_photo_usage(user_id: int) -> Tuple[int, int]:
    if user_id == OWNER_ID:
        return 0, UNLIMITED

    usage_data = load_usage()
    current_date = datetime.now().strftime("%Y-%m-%d")
    user_key = str(user_id)
    limit = DAILY_PHOTO_LIMIT

    if user_key not in usage_data:
        usage_data[user_key] = {"date": current_date, "count": 0}
    
    user_usage = usage_data[user_key]
    
    if user_usage.get("date") != current_date:
        user_usage["date"] = current_date
        user_usage["count"] = 0
    
    user_usage["count"] += 1
    
    save_usage(usage_data)
    
    return user_usage["count"], limit
