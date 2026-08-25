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

# ===== РЕЖИМ КОНТЕНТА =====
# Ровно один источник постов на процесс:
#   streamers — посты про стримеров (текст + ссылка на клип)
#   memes     — случайный мем из каналов-источников
CONTENT_MODES = ("streamers", "memes")
CONTENT_MODE = os.getenv("CONTENT_MODE", "streamers").strip().lower()
if CONTENT_MODE not in CONTENT_MODES:
    print(f"❌ Ошибка: CONTENT_MODE={CONTENT_MODE!r}, допустимо: {', '.join(CONTENT_MODES)}")
    sys.exit(1)

# ===== DEEPSEEK =====
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_VISION_MODEL = os.getenv("DEEPSEEK_VISION_MODEL", "deepseek-vl-chat")
DEEPSEEK_API_URL = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions")

# ===== ПОИСК МЕДИА =====
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

# ===== FREEKASSA =====
FREEKASSA_SHOP_ID = os.getenv("FREEKASSA_SHOP_ID", "")
FREEKASSA_SECRET1 = os.getenv("FREEKASSA_SECRET1", "")
FREEKASSA_SECRET2 = os.getenv("FREEKASSA_SECRET2", "")
FREEKASSA_API_KEY = os.getenv("FREEKASSA_API_KEY", "")
FREEKASSA_CURRENCY = os.getenv("FREEKASSA_CURRENCY", "RUB")

# ===== AURAPAY =====
AURAPAY_MERCHANT_ID = os.getenv("AURAPAY_MERCHANT_ID", "")
AURAPAY_API_KEY = os.getenv("AURAPAY_API_KEY", "")
AURAPAY_API_URL = os.getenv("AURAPAY_API_URL", "https://app.aurapay.tech")
AURAPAY_WEBHOOK_URL = os.getenv("AURAPAY_WEBHOOK_URL", "")
AURAPAY_MINIAPP_URL = os.getenv(
    "AURAPAY_MINIAPP_URL",
    "https://jameshardlp.github.io/asianbot/aura-payment.html"
)

# ===== ФАЙЛЫ =====
BROADCAST_PRICE_FILE = os.getenv("BROADCAST_PRICE_FILE", "broadcast_price.json")

# ===== ОТЛАДКА =====
if __name__ == "__main__":
    print("✅ Конфигурация загружена успешно!")
    print(f"BOT_TOKEN: {'установлен' if BOT_TOKEN else '❌ ОТСУТСТВУЕТ'}")
    print(f"OWNER_ID: {OWNER_ID}")
    print(f"CHANNEL_ID: {CHANNEL_ID or 'не задан'}")
    print(f"CONTENT_MODE: {CONTENT_MODE}")
