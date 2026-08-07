"""Состояние заказов рассылки.

`broadcast_data` и `pending_broadcasts` — разделяемое изменяемое состояние:
хендлеры и вебхуки правят те же самые словари. Меняйте их только на месте
(`d[k] = v`, `del d[k]`). Присваивание имени целиком (`broadcast_data = {}`)
разорвёт связь между модулями, и рассылки начнут молча теряться.
"""
import json
import time
import logging

from ..config import BROADCAST_PRICE_FILE

logger = logging.getLogger(__name__)

# user_id -> данные незавершённой рассылки (текст, медиа, order_id, paid)
broadcast_data = {}
# broadcast_id -> рассылка, ожидающая модерации
pending_broadcasts = {}


def load_broadcast_price() -> dict:
    """Читает цены из файла. При любой ошибке отдаёт значения по умолчанию."""
    try:
        with open(BROADCAST_PRICE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {"stars": data.get("stars", 100), "rub": data.get("rub", 100)}
    except (OSError, ValueError) as e:
        logger.warning(f"⚠️ Не удалось прочитать {BROADCAST_PRICE_FILE}: {e}")
        return {"stars": 100, "rub": 100}


def save_broadcast_price(prices: dict) -> bool:
    try:
        with open(BROADCAST_PRICE_FILE, "w", encoding="utf-8") as f:
            json.dump(prices, f, ensure_ascii=False, indent=2)
        return True
    except OSError as e:
        logger.error(f"❌ Не удалось сохранить цены: {e}")
        return False


broadcast_prices = load_broadcast_price()


def mark_order_paid(base_order_id: str, method: str) -> bool:
    """Помечает заказ оплаченным, чтобы кнопка «Проверить оплату» это увидела.

    Раньше в вебхуках был цикл, который находил заказ, писал строку в лог
    и выходил, ничего не меняя, — вебхук не влиял на состояние вообще.
    """
    for uid, info in broadcast_data.items():
        if info.get("order_id") == base_order_id:
            info["paid"] = True
            info["payment_method"] = method
            info["paid_at"] = time.time()
            logger.info(f"✅ Платёж {base_order_id} ({method}) подтверждён для {uid}")
            return True

    logger.warning(f"⚠️ Заказ {base_order_id} не найден среди активных")
    return False
