"""AuraPay: создание инвойса и проверка статуса."""
import logging
import requests
from typing import Optional

from ..config import (AURAPAY_MERCHANT_ID, AURAPAY_API_KEY,
                      AURAPAY_API_URL, AURAPAY_WEBHOOK_URL)

logger = logging.getLogger(__name__)

def create_aurapay_payment(amount: float, order_id: str, user_id: int, method: str = "card") -> Optional[dict]:
    if not AURAPAY_API_KEY or not AURAPAY_MERCHANT_ID:
        logger.error("❌ AuraPay не настроен")
        return None
    
    possible_endpoints = [
        f"{AURAPAY_API_URL}/invoice/create",
        f"{AURAPAY_API_URL}/api/invoice/create",
        f"{AURAPAY_API_URL}/v1/invoice/create",
        f"{AURAPAY_API_URL}/api/v1/invoice/create",
    ]
    
    for endpoint in possible_endpoints:
        try:
            headers = {
                "Content-Type": "application/json",
                "X-API-Key": AURAPAY_API_KEY,
                "X-Merchant-Id": AURAPAY_MERCHANT_ID
            }
            
            payload = {
                "merchant_id": AURAPAY_MERCHANT_ID,
                "order_id": order_id,
                "amount": str(amount),
                "currency": "RUB",
                "description": f"Оплата рассылки #{order_id}",
                "callback_url": f"{AURAPAY_WEBHOOK_URL}/aurapay/webhook",
                "success_url": f"{AURAPAY_WEBHOOK_URL}/aurapay-success",
                "fail_url": f"{AURAPAY_WEBHOOK_URL}/aurapay-fail",
                "payment_methods": [method] if method else ["card", "sbp", "crypto"],
                "metadata": {
                    "user_id": str(user_id),
                    "order_type": "broadcast"
                }
            }
            
            response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
            
            if response.status_code in [200, 201]:
                result = response.json()
                if result.get("payment_url"):
                    return {
                        "payment_url": result["payment_url"],
                        "payment_id": result.get("payment_id"),
                        "status": result.get("status", "pending")
                    }
                elif result.get("redirect_url"):
                    return {
                        "payment_url": result["redirect_url"],
                        "payment_id": result.get("payment_id"),
                        "status": "pending"
                    }
        except Exception as e:
            logger.error(f"❌ Ошибка AuraPay: {e}")
            continue
    
    return None

async def check_aurapay_payment_status(order_id: str) -> Optional[dict]:
    if not AURAPAY_API_KEY:
        return None
    try:
        url = f"{AURAPAY_API_URL}/invoice/status"
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": AURAPAY_API_KEY,
            "X-Merchant-Id": AURAPAY_MERCHANT_ID
        }
        payload = {"order_id": order_id}
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            result = response.json()
            return result.get("data") or result
        return None
    except Exception as e:
        logger.error(f"Ошибка проверки статуса AuraPay: {e}")
        return None
