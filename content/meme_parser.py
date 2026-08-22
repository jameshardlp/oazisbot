# content/meme_parser.py
"""Парсер мемов из публичных Telegram каналов через HTML (прямые ссылки на файлы)."""
import logging
import random
import time
import re
from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Источники мемов (публичные каналы)
MEME_SOURCES = [
    {
        "name": "videos_dolboyoba",
        "url": "https://t.me/videos_dolboyoba",
    },
    {
        "name": "shitcollection",
        "url": "https://t.me/shitcollection",
    },
    {
        "name": "postleftism",
        "url": "https://t.me/postleftism",
    },
    {
        "name": "noviop",
        "url": "https://t.me/noviop",
    }
]

class MemeParser:
    """Парсер медиа из публичных каналов через веб-страницы."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        })
        self.sent_cache = set()
        self.media_cache = []
        self.last_fetch_time = 0
        self.cache_ttl = 3600  # Обновлять раз в час
    
    def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Загружает страницу канала."""
        try:
            response = self.session.get(url, timeout=15)
            if response.status_code == 200:
                return BeautifulSoup(response.text, 'html.parser')
            logger.warning(f"Ошибка загрузки {url}: {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Ошибка загрузки {url}: {e}")
            return None
    
    def _extract_direct_file_url(self, post_elem) -> Optional[str]:
        """
        Извлекает ПРЯМУЮ ссылку на файл из HTML поста.
        Аналогично парсингу @maddysontg.
        """
        try:
            # 1. ПРЯМЫЕ ССЫЛКИ НА ФАЙЛЫ (самый надёжный способ)
            # Ищем теги <a> с прямыми ссылками на файлы
            file_links = post_elem.select('a[href*="/file/"]')
            for link in file_links:
                href = link.get('href')
                if href and not href.startswith('http'):
                    href = 'https://t.me' + href
                if href and '/file/' in href:
                    # Проверяем, что это не превью
                    if not '/preview/' in href:
                        logger.debug(f"Найдена прямая ссылка на файл: {href[:80]}...")
                        return href
            
            # 2. ФОТОГРАФИИ (через data-bem или src)
            # Ищем фото через тег <img> с data-bem
            img_elem = post_elem.select_one('img[data-bem*="photo"]')
            if img_elem:
                src = img_elem.get('src')
                if src:
                    if not src.startswith('http'):
                        src = 'https://t.me' + src
                    # Преобразуем превью в полное изображение
                    if '/preview/' in src:
                        src = src.replace('/preview/', '/file/')
                    logger.debug(f"Найдено фото: {src[:80]}...")
                    return src
            
            # Альтернативно ищем <img> с классом tgme_widget_message_photo
            img_elem = post_elem.select_one('.tgme_widget_message_photo img')
            if img_elem:
                src = img_elem.get('src')
                if src:
                    if not src.startswith('http'):
                        src = 'https://t.me' + src
                    if '/preview/' in src:
                        src = src.replace('/preview/', '/file/')
                    return src
            
            # 3. ВИДЕО (через тег <video>)
            video_elem = post_elem.select_one('video[src*="/file/"]')
            if video_elem:
                src = video_elem.get('src')
                if src:
                    if not src.startswith('http'):
                        src = 'https://t.me' + src
                    logger.debug(f"Найдено видео: {src[:80]}...")
                    return src
            
            # 4. GIF И ДРУГИЕ ДОКУМЕНТЫ
            doc_links = post_elem.select('a[href*="/file/"]')
            for link in doc_links:
                href = link.get('href')
                if href:
                    if not href.startswith('http'):
                        href = 'https://t.me' + href
                    # Проверяем расширение
                    if any(href.lower().endswith(ext) for ext in ['.gif', '.mp4', '.webm', '.webp']):
                        logger.debug(f"Найден GIF/документ: {href[:80]}...")
                        return href
            
            # 5. ССЫЛКИ НА СТОРОННИЕ ХОСТИНГИ (редко, но бывает)
            # Ищем ссылки на imgur, giphy и т.д.
            external_links = post_elem.select('a[href*="imgur.com"], a[href*="giphy.com"], a[href*="tenor.com"]')
            for link in external_links:
                href = link.get('href')
                if href:
                    # Добавляем http если нужно
                    if not href.startswith('http'):
                        href = 'https://' + href
                    logger.debug(f"Найдена внешняя ссылка: {href[:80]}...")
                    return href
            
            return None
            
        except Exception as e:
            logger.debug(f"Ошибка извлечения прямой ссылки: {e}")
            return None
    
    def _parse_media_from_post(self, post_elem) -> Optional[Dict]:
        """Извлекает медиа из одного поста."""
        try:
            # Получаем прямую ссылку на файл
            media_url = self._extract_direct_file_url(post_elem)
            if not media_url:
                return None
            
            # Определяем тип по расширению
            media_type = 'photo'
            if any(media_url.endswith(ext) for ext in ['.mp4', '.mov', '.avi']):
                media_type = 'video'
            elif any(media_url.endswith(ext) for ext in ['.gif', '.webm', '.webp']):
                media_type = 'animation'
            
            # ID поста для отслеживания повторов
            post_id_elem = post_elem.select_one('.tgme_widget_message_date a')
            post_id = None
            if post_id_elem:
                href = post_id_elem.get('href')
                if href:
                    post_id = href.split('/')[-1]
            
            return {
                'media_url': media_url,
                'media_type': media_type,
                'post_id': post_id,
                'source': 'telegram'
            }
            
        except Exception as e:
            logger.debug(f"Ошибка парсинга поста: {e}")
            return None
    
    def get_channel_media(self, source: Dict, limit: int = 100) -> List[Dict]:
        """Получает медиа из канала."""
        logger.info(f"📥 Парсинг {source['name']}...")
        soup = self._fetch_page(source['url'])
        if not soup:
            return []
        
        posts = soup.select('.tgme_widget_message')
        if not posts:
            logger.warning(f"⚠️ Нет постов в {source['name']}")
            return []
        
        media_items = []
        for post in posts[:limit]:
            media = self._parse_media_from_post(post)
            if media:
                media_items.append(media)
        
        logger.info(f"✅ Найдено {len(media_items)} медиа в {source['name']}")
        return media_items
    
    def get_all_media(self, limit_per_channel: int = 100) -> List[Dict]:
        """Собирает медиа со всех источников."""
        all_media = []
        for source in MEME_SOURCES:
            try:
                media = self.get_channel_media(source, limit_per_channel)
                all_media.extend(media)
                time.sleep(1)
            except Exception as e:
                logger.error(f"❌ Ошибка парсинга {source['name']}: {e}")
        
        random.shuffle(all_media)
        logger.info(f"📊 Всего собрано {len(all_media)} медиа")
        return all_media
    
    def get_random_meme(self) -> Optional[Dict]:
        """Возвращает случайный мем из кэша или загружает новые."""
        if time.time() - self.last_fetch_time > self.cache_ttl or not self.media_cache:
            logger.info("🔄 Обновление кэша мемов...")
            self.media_cache = self.get_all_media(limit_per_channel=100)
            self.last_fetch_time = time.time()
            if len(self.sent_cache) > 500:
                self.sent_cache = set()
        
        available = [m for m in self.media_cache if m.get('post_id') not in self.sent_cache]
        
        if not available:
            logger.info("🔄 Все мемы отправлены, загружаю новые...")
            self.sent_cache = set()
            self.media_cache = self.get_all_media(limit_per_channel=100)
            self.last_fetch_time = time.time()
            available = [m for m in self.media_cache if m.get('post_id') not in self.sent_cache]
            
            if not available:
                logger.warning("⚠️ Нет доступных мемов")
                return None
        
        chosen = random.choice(available)
        if chosen.get('post_id'):
            self.sent_cache.add(chosen['post_id'])
        
        return chosen

# Глобальный экземпляр
_meme_parser = None

def get_random_meme() -> Optional[Dict]:
    """Упрощённая функция для получения случайного мема."""
    global _meme_parser
    if _meme_parser is None:
        _meme_parser = MemeParser()
    return _meme_parser.get_random_meme()
