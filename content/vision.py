"""Проверка картинок через DeepSeek.

ВНИМАНИЕ: DEEPSEEK_VISION_MODEL по умолчанию "deepseek-vl-chat", и её, скорее
всего, нет в вашем аккаунте — тогда verify_* всегда возвращают True (fail-open).
"""
import base64
import logging
from typing import Optional

from config import DEEPSEEK_API_KEY, DEEPSEEK_VISION_MODEL, DEEPSEEK_API_URL
from content import net

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
            return True

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

        response = net.post(
            DEEPSEEK_API_URL,
            headers=headers,
            json=data,
            timeout=15,
            label=f"DeepSeek Vision ({log_label})",
        )

        if response is None:
            return True

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

def encode_image_to_base64_url(image_url: str) -> Optional[str]:
    try:
        response = net.get(image_url, timeout=10, label="загрузка картинки")
        if response is not None and response.status_code == 200:
            return base64.b64encode(response.content).decode('utf-8')
        return None
    except Exception as e:
        logger.error(f"Ошибка загрузки картинки: {e}")
        return None
