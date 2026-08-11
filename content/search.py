"""Поиск контента в различных источниках."""
import logging
import random
import re
import time
from typing import Optional, List
import requests

logger = logging.getLogger(__name__)

# Настройки
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
REQUEST_TIMEOUT = 15
MAX_RETRIES = 3
RETRY_DELAY = 2

# Маппинг ключей стримеров на английские имена для точного поиска
STREAMER_EXACT_NAMES = {
    'bratishkinoff': ['bratishkinoff', 'bratishkin', 'братишкин'],
    'sasavot': ['sasavot', 'сасавот'],
    'alina_rin': ['alina rin', 'алина рин'],
    'praden': ['praden', 'праден'],
    'buster': ['buster', 'бустер'],
    'arrowwoods': ['arrowwoods', 'аравудус'],
    'voodoosh': ['voodoosh', 'вудуш'],
    'lasqa': ['lasqa', 'ласка'],  # Только ТОЧНОЕ совпадение!
    'evelone': ['evelone', 'эвелон'],
    'nenormova': ['nenormova', 'ненормова'],
}


# ===== ПОИСК КЛИПОВ НА YOUTUBE =====

def search_youtube_clip(streamer_key: str, streamer_display: str) -> Optional[str]:
    """
    Ищет клип с участием стримера на YouTube.
    Использует строгую фильтрацию по имени.
    """
    logger.info(f"🔍 Ищу клип для {streamer_display} на YouTube...")
    
    # Получаем точные имена для поиска
    exact_names = STREAMER_EXACT_NAMES.get(streamer_key, [streamer_key.lower()])
    
    # Формируем поисковые запросы (с приоритетом на точное имя)
    search_queries = []
    
    # Основные запросы с точным именем (в кавычках)
    for name in exact_names:
        search_queries.append(f'"{name}" стрим')
        search_queries.append(f'"{name}" clip')
        search_queries.append(f'"{name}" нарезка')
        search_queries.append(f'"{name}" момент')
    
    # Дополнительные запросы без кавычек (для поиска в описании)
    for name in exact_names[:1]:  # Берём только первое имя
        search_queries.append(f'{name} стрим')
        search_queries.append(f'{name} клип')
    
    # Убираем дубликаты
    search_queries = list(dict.fromkeys(search_queries))
    random.shuffle(search_queries)
    
    # Пробуем YouTube API
    from config import YOUTUBE_API_KEY
    
    if YOUTUBE_API_KEY:
        for query in search_queries[:8]:
            try:
                url = "https://www.googleapis.com/youtube/v3/search"
                params = {
                    "part": "snippet",
                    "q": query,
                    "maxResults": 15,
                    "type": "video",
                    "key": YOUTUBE_API_KEY,
                    "order": "relevance",
                }
                
                response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    for item in data.get("items", []):
                        video_id = item["id"]["videoId"]
                        title = item["snippet"]["title"].lower()
                        description = item["snippet"].get("description", "").lower()
                        
                        # СТРОГАЯ ПРОВЕРКА: имя должно быть в названии ИЛИ описании
                        if is_name_in_content(title, description, exact_names):
                            video_url = f"https://www.youtube.com/watch?v={video_id}"
                            logger.info(f"✅ Найден клип: {video_url}")
                            logger.info(f"   Название: {item['snippet']['title']}")
                            return video_url
                    
                elif response.status_code == 403:
                    logger.warning("⚠️ YouTube API ключ неактивен или превышен лимит")
                    break
                else:
                    logger.warning(f"⚠️ Ошибка YouTube API: {response.status_code}")
                    time.sleep(RETRY_DELAY)
                    
            except Exception as e:
                logger.error(f"❌ Ошибка поиска YouTube API: {e}")
                continue
    
    # Если YouTube API не работает или нет ключа — используем веб-поиск
    logger.info("🔄 Пробую веб-поиск через Яндекс...")
    for query in search_queries[:5]:
        try:
            url = f"https://yandex.ru/search/?text={query.replace(' ', '+')}"
            response = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT
            )
            
            if response.status_code == 200:
                # Ищем ссылки на YouTube в результатах
                youtube_links = re.findall(r'https?://(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})', response.text)
                if youtube_links:
                    for video_id in youtube_links[:3]:
                        video_url = f"https://www.youtube.com/watch?v={video_id}"
                        
                        # Проверяем название видео через простой запрос
                        if verify_youtube_video_title(video_id, exact_names):
                            logger.info(f"✅ Найден клип через Яндекс: {video_url}")
                            return video_url
                    
            time.sleep(RETRY_DELAY)
            
        except Exception as e:
            logger.error(f"❌ Ошибка веб-поиска: {e}")
            continue
    
    logger.warning(f"⚠️ Не найден клип для {streamer_display}")
    return None


def is_name_in_content(title: str, description: str, exact_names: List[str]) -> bool:
    """
    Строгая проверка, что имя стримера есть в названии или описании.
    Использует границы слов, чтобы не находить частичные совпадения.
    """
    for name in exact_names:
        # Экранируем спецсимволы
        escaped_name = re.escape(name)
        
        # Проверяем с границами слов
        pattern = r'\b' + escaped_name + r'\b'
        
        # Проверяем в названии
        if re.search(pattern, title, re.IGNORECASE):
            logger.debug(f"✅ Имя '{name}' найдено в названии")
            return True
        
        # Проверяем в описании
        if description and re.search(pattern, description, re.IGNORECASE):
            logger.debug(f"✅ Имя '{name}' найдено в описании")
            return True
    
    return False


def verify_youtube_video_title(video_id: str, exact_names: List[str]) -> bool:
    """
    Проверяет название видео на YouTube через прямой запрос.
    """
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT
        )
        
        if response.status_code == 200:
            # Ищем title в HTML
            title_match = re.search(r'<title>([^<]*)</title>', response.text)
            if title_match:
                title = title_match.group(1).lower()
                for name in exact_names:
                    if re.search(r'\b' + re.escape(name) + r'\b', title, re.IGNORECASE):
                        return True
        
        return False
        
    except Exception as e:
        logger.error(f"Ошибка проверки названия видео: {e}")
        return False


# ===== ПОИСК ИЗОБРАЖЕНИЙ =====

def search_bing(query: str) -> Optional[str]:
    """Поиск изображений через Bing."""
    try:
        url = "https://www.bing.com/images/search"
        params = {
            "q": query,
            "form": "HDRSC2",
            "first": 1,
            "count": 10,
        }
        
        response = requests.get(
            url,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT
        )
        
        if response.status_code == 200:
            # Ищем ссылки на изображения
            img_pattern = r'<a class="thumb" href="([^"]+)"'
            matches = re.findall(img_pattern, response.text)
            
            for match in matches[:5]:
                if match.startswith("http"):
                    return match
        
        return None
        
    except Exception as e:
        logger.error(f"Ошибка поиска в Bing: {e}")
        return None


def search_google_direct(query: str) -> Optional[str]:
    """Поиск изображений через Google (прямой запрос)."""
    try:
        url = "https://www.google.com/search"
        params = {
            "q": query,
            "tbm": "isch",
            "ijn": 0,
        }
        
        response = requests.get(
            url,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT
        )
        
        if response.status_code == 200:
            # Ищем ссылки на изображения
            img_pattern = r'"https?://[^"]+\.(?:jpg|jpeg|png|gif|webp)"'
            matches = re.findall(img_pattern, response.text)
            
            if matches:
                # Убираем кавычки
                img_url = matches[0].strip('"')
                return img_url
        
        return None
        
    except Exception as e:
        logger.error(f"Ошибка поиска в Google: {e}")
        return None


def search_yandex(query: str) -> Optional[str]:
    """Поиск изображений через Яндекс."""
    try:
        url = "https://yandex.ru/images/search"
        params = {
            "text": query,
            "rpt": "imageview",
            "img_url": "",
        }
        
        response = requests.get(
            url,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT
        )
        
        if response.status_code == 200:
            # Ищем ссылки на изображения
            img_pattern = r'"https?://[^"]+\.(?:jpg|jpeg|png|gif|webp)"'
            matches = re.findall(img_pattern, response.text)
            
            if matches:
                img_url = matches[0].strip('"')
                return img_url
        
        return None
        
    except Exception as e:
        logger.error(f"Ошибка поиска в Яндекс: {e}")
        return None


def search_pexels(query: str) -> Optional[str]:
    """Поиск изображений через Pexels API."""
    try:
        from config import PEXELS_KEY
        
        if not PEXELS_KEY:
            return None
        
        url = "https://api.pexels.com/v1/search"
        headers = {"Authorization": PEXELS_KEY}
        params = {
            "query": query,
            "per_page": 5,
            "orientation": "portrait",
        }
        
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=REQUEST_TIMEOUT
        )
        
        if response.status_code == 200:
            data = response.json()
            photos = data.get("photos", [])
            
            if photos:
                photo = random.choice(photos)
                return photo.get("src", {}).get("large")
        
        return None
        
    except Exception as e:
        logger.error(f"Ошибка поиска в Pexels: {e}")
        return None


def search_streamer_screenshot(streamer_key: str, streamer_display: str) -> Optional[str]:
    """
    Поиск скрина со стрима.
    Ищет по имени стримера на Twitch или YouTube.
    """
    try:
        # Ищем скриншоты на Twitch
        queries = [
            f"{streamer_display} twitch screenshot",
            f"{streamer_display} stream screenshot",
            f"{streamer_display} стрим скрин",
        ]
        
        random.shuffle(queries)
        
        for query in queries[:2]:
            # Пробуем через Bing
            photo = search_bing(query)
            if photo:
                return photo
            
            # Пробуем через Google
            photo = search_google_direct(query)
            if photo:
                return photo
        
        return None
        
    except Exception as e:
        logger.error(f"Ошибка поиска скрина для {streamer_display}: {e}")
        return None
