"""FreeKassa: подпись, ссылка на оплату, статус заказа."""
import hashlib
import hmac
import logging
import requests
from typing import Optional
from urllib.parse import urlencode

from ..config import (FREEKASSA_SHOP_ID, FREEKASSA_SECRET1, FREEKASSA_SECRET2,
                      FREEKASSA_API_KEY, FREEKASSA_CURRENCY)

logger = logging.getLogger(__name__)

def generate_freekassa_signature(shop_id: str, amount: str, order_id: str) -> str:
    sign_str = f"{shop_id}:{amount}:{FREEKASSA_SECRET1}:{FREEKASSA_CURRENCY}:{order_id}"
    return hashlib.md5(sign_str.encode()).hexdigest()

def verify_freekassa_webhook_signature(data: dict) -> bool:
    required_fields = ['MERCHANT_ID', 'AMOUNT', 'MERCHANT_ORDER_ID', 'SIGN']
    for field in required_fields:
        if field not in data:
            return False
    
    shop_id = str(data.get('MERCHANT_ID'))
    amount = str(data.get('AMOUNT'))
    order_id = str(data.get('MERCHANT_ORDER_ID'))
    sign = str(data.get('SIGN'))
    
    # ВНИМАНИЕ: подпись уведомления FreeKassa считается БЕЗ currency —
    # md5(merchant_id:AMOUNT:secret2:MERCHANT_ORDER_ID). Прежняя строка
    # включала FREEKASSA_CURRENCY, из-за чего ни одно уведомление не проходило
    # проверку. Сверьте формулу с актуальной документацией вашего аккаунта.
    sign_str = f"{shop_id}:{amount}:{FREEKASSA_SECRET2}:{order_id}"
    expected_sign = hashlib.md5(sign_str.encode()).hexdigest()
    return hmac.compare_digest(sign.lower(), expected_sign)

def create_freekassa_payment_link(amount: float, order_id: str, description: str = "") -> str:
    if not FREEKASSA_SHOP_ID or not FREEKASSA_SECRET1:
        logger.error("❌ FreeKassa не настроен")
        return ""
    
    shop_id = str(FREEKASSA_SHOP_ID)
    amount_int = int(amount)
    amount_str = str(amount_int)
    order_id_str = str(order_id)
    
    signature = generate_freekassa_signature(shop_id, amount_str, order_id_str)
    
    params = {
        "m": shop_id,
        "oa": amount_str,
        "currency": FREEKASSA_CURRENCY,
        "o": order_id_str,
        "s": signature,
    }
    if description:
        params["description"] = description[:255]
    
    return f"https://pay.fk.money/?{urlencode(params)}"

async def check_freekassa_payment_status(order_id: str) -> Optional[dict]:
    if not FREEKASSA_API_KEY:
        return None
    try:
        url = "https://api.freekassa.ru/v1/orders/status"
        headers = {"Content-Type": "application/json"}
        data = {
            "merchant_id": FREEKASSA_SHOP_ID,
            "api_key": FREEKASSA_API_KEY,
            "order_id": order_id
        }
        response = requests.post(url, headers=headers, json=data, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "success":
                return result.get("data", {})
        return None
    except Exception as e:
        logger.error(f"Ошибка проверки статуса: {e}")
        return None
