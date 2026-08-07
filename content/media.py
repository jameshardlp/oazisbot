"""Подбор медиа для поста.

Порядок: клип с YouTube -> скрин со стрима -> фото стримера -> фото Азии.
"""
import random
import logging
from typing import Optional, Tuple

from filters import check_date_in_content, is_photo_valid
from streamers import STREAMER_QUERIES, ASIAN_QUERIES, STREAMER_KEYS
from search import (search_bing, search_google_direct, search_yandex, search_pexels,
                     search_streamer_screenshot, search_youtube_clip)
from vision import verify_photo_with_deepseek, verify_asia_photo_with_deepseek

logger = logging.getLogger(__name__)

def get_streamer_photo(streamer_name: str) -> Optional[str]:
    """Поиск фото стримера"""
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
                            logger.info(f"✅ Найдено новое фото для {streamer_name}")
                            return photo
            except Exception as e:
                logger.error(f"Ошибка поиска для {streamer_name} в {source_name}: {e}")
                continue
    
    logger.warning(f"⚠️ Не найдено фото для {streamer_name}")
    return None

def get_asia_photo() -> Optional[str]:
    """Поиск фото азиатской модели для темы asia"""
    queries = ASIAN_QUERIES.copy()
    random.shuffle(queries)
    
    search_functions = [
        (search_bing, "Bing Картинки"),
        (search_google_direct, "Google Картинки"),
        (search_yandex, "Яндекс Картинки"),
        (search_pexels, "Pexels"),
    ]
    random.shuffle(search_functions)
    
    for query in queries[:5]:
        for search_func, source_name in search_functions:
            try:
                logger.info(f"Поиск азиатского фото в {source_name}: {query}")
                photo = search_func(query)
                if photo:
                    if check_date_in_content("", photo):
                        if is_photo_valid(photo):
                            if verify_asia_photo_with_deepseek(photo):
                                logger.info(f"✅ Найдено азиатское фото")
                                return photo
            except Exception as e:
                logger.error(f"Ошибка поиска азиатского фото в {source_name}: {e}")
                continue
    
    logger.warning("⚠️ Не найдено подходящее азиатское фото")
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

async def get_random_photo(style: str = "streamer", streamer_key: str = None, history=None) -> Optional[str]:
    """Получает случайное фото в зависимости от стиля"""
    if history is None:
        history = []
    
    if style == 'streamer' and streamer_key:
        photo = get_streamer_photo(streamer_key)
        if photo and photo not in history:
            if check_date_in_content("", photo):
                return photo
        elif photo and photo in history:
            logger.info("⏭️ Фото уже использовалось")
            return None
        
        logger.info("🔄 Пробую найти другого стримера...")
        streamers = list(STREAMER_KEYS)
        random.shuffle(streamers)
        
        for streamer in streamers:
            if streamer == streamer_key:
                continue
            photo = get_streamer_photo(streamer)
            if photo and photo not in history:
                if check_date_in_content("", photo):
                    return photo
        
        logger.warning("⚠️ Не найдены фото стримеров, пробую общий поиск")
        fallback_queries = ["russian streamer face", "twitch streamer russian", "streamer portrait"]
        random.shuffle(fallback_queries)
        
        search_functions = [
            (search_bing, "Bing Картинки"),
            (search_google_direct, "Google Картинки"),
            (search_yandex, "Яндекс Картинки"),
        ]
        random.shuffle(search_functions)
        
        for query in fallback_queries[:2]:
            for search_func, source_name in search_functions[:2]:
                try:
                    photo = search_func(query)
                    if photo and photo not in history:
                        if check_date_in_content("", photo):
                            return photo
                except Exception as e:
                    continue
    
    elif style == 'asia':
        photo = get_asia_photo()
        if photo and photo not in history:
            if check_date_in_content("", photo):
                return photo
        elif photo and photo in history:
            logger.info("⏭️ Азиатское фото уже использовалось")
            return None
        
        logger.info("🔄 Пробую найти другое азиатское фото...")
        photo = get_asia_photo()
        if photo and photo not in history:
            if check_date_in_content("", photo):
                return photo
    
    logger.error("❌ Не удалось найти подходящее фото!")
    return None
