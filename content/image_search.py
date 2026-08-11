"""Поиск фото стримеров через Яндекс.Картинки.

Использует поиск по нику стримера на английском языке.
"""
import logging
import random
import re
import time
from typing import Optional, List
import requests
from urllib.parse import quote

logger = logging.getLogger(__name__)

# Настройки
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
REQUEST_TIMEOUT = 15
MAX_RETRIES = 3
RETRY_DELAY = 2

# Маппинг ключей стримеров на английские имена для поиска
STREAMER_SEARCH_NAMES = {
    'bratishkinoff': 'Bratishkinoff',
    'sasavot': 'Sasavot',
    'alina_rin': 'Alina Rin',
    'praden': 'Praden',
    'buster': 'Buster',
    'arrowwoods': 'Arrowwoods',
    'voodoosh': 'Voodoosh',
    'lasqa': 'Lasqa',
    'evelone': 'Evelone',
    'nenormova': 'Nenormova',
}

def search_yandex_images(query: str, limit: int = 10) -> List[str]:
    """
    Ищет изображения через Яндекс.Картинки.
    
    Args:
        query: Поисковый запрос (ник стримера на английском)
        limit: Максимальное количество результатов
        
    Returns:
        Список URL изображений
    """
    logger.info(f"🔍 Ищу изображения по запросу: {query}")
    
    encoded_query = quote(query)
    urls = []
    
    # Яндекс.Картинки использует пагинацию через параметр p
    # Пробуем получить несколько страниц
    for page in range(0, min(3, (limit // 10) + 1)):
        url = f"https://yandex.ru/images/search?text={encoded_query}&p={page}"
        
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.get(
                    url,
                    headers={
                        'User-Agent': USER_AGENT,
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                    },
                    timeout=REQUEST_TIMEOUT
                )
                
                if response.status_code == 200:
                    # Парсим URL изображений из HTML
                    # Яндекс использует data-bem для хранения информации о картинках
                    image_urls = parse_yandex_images(response.text)
                    
                    if image_urls:
                        urls.extend(image_urls)
                        logger.info(f"✅ Найдено {len(image_urls)} изображений на странице {page+1}")
                        break
                    else:
                        logger.warning(f"⚠️ Не найдено изображений на странице {page+1}")
                        break
                elif response.status_code == 429:
                    wait_time = RETRY_DELAY * (attempt + 1)
                    logger.warning(f"Rate limit, ждём {wait_time} секунд...")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.warning(f"Ошибка HTTP {response.status_code} (попытка {attempt + 1})")
                    time.sleep(RETRY_DELAY)
                    continue
                    
            except Exception as e:
                logger.error(f"Ошибка при запросе: {e}")
                time.sleep(RETRY_DELAY)
                continue
        
        # Если набрали нужное количество, выходим
        if len(urls) >= limit:
            break
        
        # Небольшая задержка между страницами
        time.sleep(0.5)
    
    # Возвращаем уникальные URL (убираем дубликаты)
    unique_urls = list(dict.fromkeys(urls))
    logger.info(f"✅ Всего найдено {len(unique_urls)} уникальных изображений")
    
    return unique_urls[:limit]

def parse_yandex_images(html: str) -> List[str]:
    """
    Парсит URL изображений из HTML Яндекс.Картинок.
    """
    urls = []
    
    # Ищем данные в data-bem атрибутах
    # Яндекс хранит информацию о картинках в data-bem="{"img":{"src":"..."}}"
    bem_pattern = r'data-bem="([^"]*)"'
    bem_matches = re.findall(bem_pattern, html)
    
    for bem_data in bem_matches:
        try:
            # Парсим JSON из data-bem
            import json
            data = json.loads(bem_data)
            if 'img' in data and 'src' in data['img']:
                src = data['img']['src']
                if src.startswith('//'):
                    src = 'https:' + src
                if src.startswith('http'):
                    urls.append(src)
        except:
            pass
    
    # Альтернативный поиск: ищем img с атрибутом src
    if not urls:
        img_pattern = r'<img[^>]+src="([^"]+)"[^>]*>'
        img_matches = re.findall(img_pattern, html)
        for src in img_matches:
            if src.startswith('//'):
                src = 'https:' + src
            if src.startswith('http') and not src.endswith('.gif'):
                # Исключаем маленькие иконки
                if 'favicon' not in src and 'logo' not in src:
                    urls.append(src)
    
    # Чистим URL от параметров
    clean_urls = []
    for url in urls:
        # Убираем параметры после ? (кроме тех, что нужны)
        if '?' in url:
            base_url = url.split('?')[0]
            # Проверяем, что это не превьюшка
            if not base_url.endswith('.jpg') and not base_url.endswith('.png') and not base_url.endswith('.jpeg'):
                # Если это не прямое изображение, оставляем как есть
                clean_urls.append(url)
            else:
                clean_urls.append(base_url)
        else:
            clean_urls.append(url)
    
    return clean_urls

def get_streamer_photo(streamer_key: str, limit: int = 5) -> Optional[str]:
    """
    Получает фото стримера по его ключу.
    
    Args:
        streamer_key: Ключ стримера из STREAMER_INFO
        limit: Количество попыток найти фото
        
    Returns:
        URL фото или None
    """
    # Получаем имя для поиска
    search_name = STREAMER_SEARCH_NAMES.get(streamer_key)
    if not search_name:
        logger.warning(f"⚠️ Неизвестный стример: {streamer_key}")
        return None
    
    # Ищем изображения
    images = search_yandex_images(search_name, limit=limit)
    
    if not images:
        logger.warning(f"⚠️ Не найдено изображений для {search_name}")
        return None
    
    # Возвращаем случайное изображение из найденных
    selected = random.choice(images)
    logger.info(f"✅ Выбрано фото для {search_name}: {selected[:100]}...")
    return selected

def get_random_photo() -> Optional[str]:
    """
    Получает случайное фото (для постов про Азию).
    """
    from content.streamers import ASIAN_QUERIES
    
    query = random.choice(ASIAN_QUERIES)
    images = search_yandex_images(query, limit=5)
    
    if not images:
        return None
    
    return random.choice(images)

# Тестирование
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    print("\n" + "="*60)
    print("🧪 ТЕСТИРОВАНИЕ ПОИСКА ФОТО")
    print("="*60 + "\n")
    
    # Тест: поиск фото Братишкина
    print("🔍 Поиск фото для Bratishkinoff...")
    photo = get_streamer_photo('bratishkinoff')
    if photo:
        print(f"✅ Найдено фото: {photo}")
    else:
        print("❌ Фото не найдено")
    
    print("\n" + "-"*60 + "\n")
    
    # Тест: поиск фото для Алины Рин
    print("🔍 Поиск фото для Alina Rin...")
    photo = get_streamer_photo('alina_rin')
    if photo:
        print(f"✅ Найдено фото: {photo}")
    else:
        print("❌ Фото не найдено")