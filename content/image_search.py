"""Поиск фото стримеров через Яндекс.Картинки."""
import logging
import random
import re
import time
from typing import Optional, List
import requests
from urllib.parse import quote

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
REQUEST_TIMEOUT = 15
MAX_RETRIES = 3
RETRY_DELAY = 2

STREAMER_SEARCH_NAMES = {
    'bratishkinoff': 'Bratishkinoff',
    'sasavot': 'Sasavot',
    'alina_rin': 'Alina Rin',
    'praden': 'Praden',
    'buster': 'Buster',
    'arrowwoods': 'Arrowwoods',
    'voodoosh': 'Voodoosh',
    'evelone': 'Evelone',
    'nenormova': 'Nenormova',
    't2x2': 'T2x2',
    'dinablin': 'Dinablin',
    'olyashaa': 'Olyashaa',
    'guit88man': 'Guit88man',
    'recrent': 'Recrent',
    'koryamc': 'Koryamc',
    'karmikkoala': 'Karmikkoala',
}


def search_yandex_images(query: str, limit: int = 10) -> List[str]:
    """Ищет изображения через Яндекс.Картинки и возвращает прямые ссылки."""
    logger.info(f"🔍 Ищу изображения по запросу: {query}")
    
    encoded_query = quote(query)
    urls = []
    
    for page in range(0, min(2, (limit // 10) + 1)):
        url = f"https://yandex.ru/images/search?text={encoded_query}&p={page}"
        
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.get(
                    url,
                    headers={'User-Agent': USER_AGENT},
                    timeout=REQUEST_TIMEOUT
                )
                
                if response.status_code == 200:
                    # Получаем прямые ссылки на изображения
                    image_urls = parse_yandex_images(response.text)
                    
                    if image_urls:
                        urls.extend(image_urls)
                        logger.info(f"✅ Найдено {len(image_urls)} изображений")
                        break
                elif response.status_code == 429:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                else:
                    time.sleep(RETRY_DELAY)
                    continue
                    
            except Exception as e:
                logger.error(f"Ошибка при запросе: {e}")
                time.sleep(RETRY_DELAY)
                continue
        
        if len(urls) >= limit:
            break
        time.sleep(0.5)
    
    # Фильтруем только прямые ссылки
    valid_urls = []
    for url in urls:
        if url.startswith('http') and any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
            valid_urls.append(url)
    
    unique_urls = list(dict.fromkeys(valid_urls))
    logger.info(f"✅ Найдено {len(unique_urls)} прямых ссылок на изображения")
    return unique_urls[:limit]


def parse_yandex_images(html: str) -> List[str]:
    """Парсит прямые ссылки на изображения из HTML Яндекс.Картинок."""
    urls = []
    
    # 1. Ищем через data-bem
    bem_pattern = r'data-bem="([^"]*)"'
    bem_matches = re.findall(bem_pattern, html)
    
    for bem_data in bem_matches:
        try:
            import json
            data = json.loads(bem_data)
            # Ищем src в разных структурах
            if 'img' in data and 'src' in data['img']:
                src = data['img']['src']
                if src.startswith('//'):
                    src = 'https:' + src
                if src.startswith('http') and not 'preview' in src:
                    urls.append(src)
            # Альтернативная структура
            if 'src' in data:
                src = data['src']
                if src.startswith('//'):
                    src = 'https:' + src
                if src.startswith('http') and not 'preview' in src:
                    urls.append(src)
        except:
            pass
    
    # 2. Ищем через теги img
    img_pattern = r'<img[^>]+src="(https?://[^"]+\.(?:jpg|jpeg|png|gif|webp))"'
    img_matches = re.findall(img_pattern, html, re.IGNORECASE)
    for src in img_matches:
        if 'preview' not in src and 'logo' not in src and 'favicon' not in src:
            urls.append(src)
    
    # 3. Ищем через теги a с изображениями
    a_pattern = r'<a[^>]+href="(https?://[^"]+\.(?:jpg|jpeg|png|gif|webp))"'
    a_matches = re.findall(a_pattern, html, re.IGNORECASE)
    for src in a_matches:
        if 'preview' not in src:
            urls.append(src)
    
    return urls


def get_streamer_photo(streamer_key: str, limit: int = 5) -> Optional[str]:
    """Получает фото стримера по его ключу."""
    search_name = STREAMER_SEARCH_NAMES.get(streamer_key)
    if not search_name:
        logger.warning(f"⚠️ Неизвестный стример: {streamer_key}")
        return None
    
    # Ищем изображения
    images = search_yandex_images(search_name, limit=limit)
    
    if not images:
        logger.warning(f"⚠️ Не найдено изображений для {search_name}")
        return None
    
    # Выбираем случайное и проверяем доступность
    for _ in range(3):  # 3 попытки
        selected = random.choice(images)
        if is_url_accessible(selected):
            logger.info(f"✅ Выбрано фото для {search_name}")
            return selected
    
    logger.warning(f"⚠️ Не удалось найти доступное фото для {search_name}")
    return None


def is_url_accessible(url: str) -> bool:
    """Проверяет, доступен ли URL."""
    try:
        response = requests.head(url, timeout=5, allow_redirects=True)
        return response.status_code == 200
    except:
        return False


def get_random_photo() -> Optional[str]:
    """Получает случайное фото для постов про Азию."""
    from content.streamers import ASIAN_QUERIES
    
    query = random.choice(ASIAN_QUERIES)
    images = search_yandex_images(query, limit=5)
    
    if not images:
        return None
    
    for _ in range(3):
        selected = random.choice(images)
        if is_url_accessible(selected):
            return selected
    
    return None
