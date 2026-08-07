"""Конфигурация бота: переменные окружения, константы, пути к файлам.

Единственное место, где читается окружение. Раньше FREEKASSA_*, DEEPSEEK_API_KEY
и YOUTUBE_API_KEY дублировались в двух модулях и могли разъехаться.
"""
import os
import sys

# ===== ПРОВЕРКА ОБЯЗАТЕЛЬНЫХ ПЕРЕМЕННЫХ =====
def get_required_env(key: str) -> str:
    """Получить обязательную переменную окружения или завершить работу."""
    value = os.getenv(key)
    if value is None or value == "":
        print(f"❌ Ошибка: обязательная переменная {key} не задана!")
        sys.exit(1)
    return value

def get_env_int(key: str, default: int) -> int:
    """Получить целочисленную переменную с проверкой."""
    try:
        return int(os.getenv(key, default))
    except ValueError:
        print(f"⚠️ Ошибка в {key}, используется значение по умолчанию: {default}")
        return default

# ===== TELEGRAM =====
BOT_TOKEN = get_required_env("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # может быть None (если канал не задан)
OWNER_ID = get_env_int("OWNER_ID", 0)
STARS_CHANNEL_ID = get_env_int("STARS_CHANNEL_ID", -1003893727881)

# ===== DEEPSEEK =====
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_VISION_MODEL = os.getenv("DEEPSEEK_VISION_MODEL", "deepseek-vl-chat")
DEEPSEEK_API_URL = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions")

# ===== ПОИСК МЕДИА =====
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
PEXELS_KEY = os.getenv("PEXELS_KEY", "")

# ===== FREEKASSA =====
FREEKASSA_SHOP_ID = os.getenv("FREEKASSA_SHOP_ID", "")
FREEKASSA_SECRET1 = os.getenv("FREEKASSA_SECRET1", "")
FREEKASSA_SECRET2 = os.getenv("FREEKASSA_SECRET2", "")
FREEKASSA_API_KEY = os.getenv("FREEKASSA_API_KEY", "")
FREEKASSA_CURRENCY = os.getenv("FREEKASSA_CURRENCY", "RUB")

# ===== AURAPAY =====
AURAPAY_MERCHANT_ID = os.getenv("AURAPAY_MERCHANT_ID", "6a70ee5492726")
AURAPAY_API_KEY = os.getenv("AURAPAY_API_KEY", "")
AURAPAY_API_URL = os.getenv("AURAPAY_API_URL", "https://app.aurapay.tech")
AURAPAY_WEBHOOK_URL = os.getenv("AURAPAY_WEBHOOK_URL", "")
AURAPAY_MINIAPP_URL = os.getenv(
    "AURAPAY_MINIAPP_URL",
    "https://jameshardlp.github.io/asianbot/aura-payment.html"
)

# ===== ПОВЕДЕНИЕ (можно вынести в .env) =====
SEND_DELAY = float(os.getenv("SEND_DELAY", 3.0))
MIN_POST_INTERVAL = int(os.getenv("MIN_POST_INTERVAL", 2 * 60 * 60))
RATE_LIMIT_SECONDS = int(os.getenv("RATE_LIMIT_SECONDS", 3))
DAILY_PHOTO_LIMIT = int(os.getenv("DAILY_PHOTO_LIMIT", 10))
MODERATION_DELAY = int(os.getenv("MODERATION_DELAY", 300))

# ===== ФАЙЛЫ =====
USERS_FILE = os.getenv("USERS_FILE", "users.json")
HISTORY_FILE = os.getenv("HISTORY_FILE", "history.json")
SCHEDULE_FILE = os.getenv("SCHEDULE_FILE", "schedule.json")
USAGE_FILE = os.getenv("USAGE_FILE", "usage.json")
BROADCAST_PRICE_FILE = os.getenv("BROADCAST_PRICE_FILE", "broadcast_price.json")

# ===== КОНСТАНТЫ =====
UNLIMITED = float('inf')

# ===== ОТЛАДКА =====
if __name__ == "__main__":
    print("✅ Конфигурация загружена успешно!")
    print(f"BOT_TOKEN: {'установлен' if BOT_TOKEN else '❌ ОТСУТСТВУЕТ'}")
    print(f"OWNER_ID: {OWNER_ID}")
    print(f"CHANNEL_ID: {CHANNEL_ID or 'не задан'}")
