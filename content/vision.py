"""Проверка и описание картинок через DeepSeek.

ВНИМАНИЕ: DEEPSEEK_VISION_MODEL по умолчанию "deepseek-vl-chat", и её, скорее
всего, нет в вашем аккаунте — тогда verify_* всегда возвращают True (fail-open),
а analyze_photo_for_comment молча отдаёт None.
"""
import base64
import logging
import requests
from typing import Optional

from config import DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_VISION_MODEL, DEEPSEEK_API_URL

logger = logging.getLogger(__name__)

def _ask_deepseek_about_image(image_url: str, question: str, log_label: str) -> bool:
    """Задаёт DeepSeek да/нет вопрос о картинке.

    ВНИМАНИЕ: при любой ошибке API возвращает True (fail-open) — так было
    в исходном коде, чтобы недоступность DeepSeek не блокировала посты.
    """
    if not DEEPSEEK_API_KEY:
        logger.warning("⚠️ Нет DeepSeek API ключа для проверки фото")
        return True

    try:
        base64_image = encode_image_to_base64_url(image_url)
        if not base64_image:
            return False

        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": DEEPSEEK_VISION_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {"type": "image_url",
                         "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                }
            ],
            "max_tokens": 10,
            "temperature": 0.1
        }

        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=15)

        if response.status_code == 200:
            answer = response.json()["choices"][0]["message"]["content"].strip().upper()
            logger.info(f"🔍 DeepSeek проверка {log_label}: {answer}")
            return "ДА" in answer

        logger.error(f"❌ Ошибка проверки фото: {response.status_code}")
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка проверки фото через DeepSeek: {e}")
        return True

def verify_photo_with_deepseek(image_url: str, streamer_name: str) -> bool:
    """Проверяет через DeepSeek, что на фото изображен нужный стример"""
    return _ask_deepseek_about_image(
        image_url,
        f"Посмотри на это фото. Это стример {streamer_name}? Ответь только 'ДА' или 'НЕТ'.",
        f"фото для {streamer_name}"
    )

def verify_asia_photo_with_deepseek(image_url: str) -> bool:
    """Проверяет через DeepSeek, что на фото азиатская модель/девушка"""
    return _ask_deepseek_about_image(
        image_url,
        "Посмотри на это фото. Это азиатская девушка/модель? Ответь только 'ДА' или 'НЕТ'.",
        "азиатского фото"
    )

def encode_image_to_base64_url(image_url: str) -> str:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(image_url, headers=headers, timeout=10)
        if response.status_code == 200:
            return base64.b64encode(response.content).decode('utf-8')
        return None
    except Exception as e:
        logger.error(f"Ошибка загрузки картинки: {e}")
        return None

async def analyze_photo_for_comment(image_url: str) -> Optional[str]:
    if not DEEPSEEK_API_KEY:
        return None
    
    try:
        base64_image = encode_image_to_base64_url(image_url)
        if not base64_image:
            return None
        
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": DEEPSEEK_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Коротко опиши что на фото. 1-2 предложения. Грубо, с юмором. Используй мат."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 150,
            "temperature": 1.1
        }
        
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            comment = result["choices"][0]["message"]["content"].strip()
            logger.info(f"🖼️ Комментарий к фото: {comment}")
            return comment
        return None
    except Exception as e:
        logger.error(f"Ошибка анализа фото: {e}")
        return None
