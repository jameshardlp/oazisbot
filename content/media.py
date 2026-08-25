"""Подбор медиа для поста про стримера.

Порядок: клип с YouTube -> скрин со стрима -> фото стримера.
"""
import random
import logging
from typing import Optional, Tuple

from content.filters import check_date_in_content
from content.streamers import STREAMER_QUERIES
from content.search import (search_bing, search_google_direct, search_yandex,
                     search_streamer_screenshot, search_youtube_clip)
from content.vision import verify_photo_with_deepseek
# Импортируем новый поиск через Яндекс.Картинки
from content.image_search import get_streamer_photo as get_streamer_photo_yandex

logger = logging.getLogger(__name__)

def get_streamer_photo(streamer_name: str) -> Optional[str]:
    """Поиск фото стримера через Яндекс.Картинки (основной) + резервные источники"""

    # ===== ОСНОВНОЙ ПОИСК ЧЕРЕЗ ЯНДЕКС.КАРТИНКИ =====
    logger.info(f"🔍 Поиск фото для {streamer_name} через Яндекс.Картинки...")
    try:
        # Используем новый поиск через Яндекс.Картинки
        yandex_photo = get_streamer_photo_yandex(streamer_name, limit=10)
        if yandex_photo:
            if check_date_in_content("", yandex_photo):
                if verify_photo_with_deepseek(yandex_photo, streamer_name):
                    logger.info(f"✅ Найдено фото для {streamer_name} через Яндекс.Картинки")
                    return yandex_photo
                else:
                    logger.warning(f"⚠️ Фото не прошло верификацию DeepSeek, пробую другие источники...")
            else:
                logger.warning(f"⚠️ Фото не прошло проверку даты, пробую другие источники...")
    except Exception as e:
        logger.error(f"❌ Ошибка поиска через Яндекс.Картинки: {e}")

    # ===== РЕЗЕРВНЫЙ ПОИСК (старые методы) =====
    logger.info(f"🔍 Резервный поиск фото для {streamer_name} через другие источники...")

    queries = STREAMER_QUERIES.get(streamer_name, [])
    if not queries:
        return None

    random.shuffle(queries)

    search_functions = [
        (search_bing, "Bing Картинки"),
        (search_google_direct, "Google Картинки"),
        (search_yandex, "Яндекс Картинки"),
    ]
    random.shuffle(search_functions)

    for query in queries:
        for search_func, source_name in search_functions:
            try:
                logger.info(f"Поиск фото для {streamer_name} в {source_name}: {query}")
                photo = search_func(query)
                if photo:
                    if check_date_in_content("", photo):
                        if verify_photo_with_deepseek(photo, streamer_name):
                            logger.info(f"✅ Найдено новое фото для {streamer_name} через {source_name}")
                            return photo
            except Exception as e:
                logger.error(f"Ошибка поиска для {streamer_name} в {source_name}: {e}")
                continue

    logger.warning(f"⚠️ Не найдено фото для {streamer_name}")
    return None

# ===== ФУНКЦИЯ ПОЛУЧЕНИЯ МЕДИА ДЛЯ СТРИМЕРА =====

def get_streamer_media(streamer_key: str, streamer_display: str) -> Tuple[Optional[str], str]:
    """Получает медиа для стримера: сначала клип, если нет - скрин/фото"""
    logger.info(f"📹 Ищу клип для {streamer_display}...")
    clip = search_youtube_clip(streamer_key, streamer_display)
    if clip:
        return clip, 'clip'

    logger.info(f"🖼️ Клип не найден, ищу фото для {streamer_display}...")

    screenshot = search_streamer_screenshot(streamer_key, streamer_display)
    if screenshot:
        return screenshot, 'photo'

    photo = get_streamer_photo(streamer_key)
    if photo:
        return photo, 'photo'

    logger.warning(f"⚠️ Не найдено ни клипа, ни фото для {streamer_display}")
    return None, 'none'
