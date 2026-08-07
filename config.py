"""Конфигурация бота: переменные окружения, константы, пути к файлам.

Единственное место, где читается окружение. Раньше FREEKASSA_*, DEEPSEEK_API_KEY
и YOUTUBE_API_KEY дублировались в двух модулях и могли разъехаться.
"""
import os

# ===== TELEGRAM =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OWNER_ID = int(os.getenv("OWNER_ID", 0))
# Канал, в котором бот должен быть админом для приёма Telegram Stars
STARS_CHANNEL_ID = -1003893727881

# ===== DEEPSEEK =====
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = "deepseek-chat"
# Модель для картинок. deepseek-chat текстовая и на image_url отвечает ошибкой,
# поэтому проверка фото сейчас всегда fail-open. Задайте рабочую vision-модель
# через DEEPSEEK_VISION_MODEL, иначе проверка картинок фактически отключена.
DEEPSEEK_VISION_MODEL = os.getenv("DEEPSEEK_VISION_MODEL", "deepseek-vl-chat")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

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

# ===== ПОВЕДЕНИЕ =====
SEND_DELAY = 3.0                    # пауза между сообщениями при рассылке
MIN_POST_INTERVAL = 2 * 60 * 60     # минимум между автопостами
RATE_LIMIT_SECONDS = 3              # антифлуд на пользователя
DAILY_PHOTO_LIMIT = 10              # лимит /photo в сутки
UNLIMITED = float('inf')
MODERATION_DELAY = 300              # пауза между одобрением и публикацией

# ===== ФАЙЛЫ =====
USERS_FILE = "users.json"
HISTORY_FILE = "history.json"
SCHEDULE_FILE = "schedule.json"
USAGE_FILE = "usage.json"
BROADCAST_PRICE_FILE = "broadcast_price.json"
