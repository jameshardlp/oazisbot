# content/meme_parser.py
"""Парсер мемов из публичных Telegram каналов через HTML."""
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
    """Парсер медиа из публичных каналов."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
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
            return None
        except Exception as e:
            logger.error(f"Ошибка загрузки {url}: {e}")
            return None
    
    def _parse_media_from_post(self, post_elem) -> Optional[Dict]:
        """Извлекает медиа из одного поста."""
        try:
            # Ищем разные типы медиа
            media_elem = post_elem.select_one('.tgme_widget_message_photo_wrap, .tgme_widget_message_video_wrap, .tgme_widget_message_document_wrap')
            if not media_elem:
                return None
            
            # ID поста
            post_id_elem = post_elem.select_one('.tgme_widget_message_date a')
            post_id = None
            if post_id_elem:
                href = post_id_elem.get('href')
                if href:
                    post_id = href.split('/')[-1]
            
            media_type = None
            media_url = None
            
            # Фото
            photo_elem = post_elem.select_one('.tgme_widget_message_photo_wrap img')
            if photo_elem:
                media_type = 'photo'
                media_url = photo_elem.get('src')
                if media_url and not media_url.startswith('http'):
                    media_url = 'https://t.me' + media_url
                if media_url and '/preview/' in media_url:
                    media_url = media_url.replace('/preview/', '/file/')
            
            # Видео
            video_elem = post_elem.select_one('.tgme_widget_message_video_wrap video')
            if not media_url and video_elem:
                media_type = 'video'
                media_url = video_elem.get('src')
                if media_url and not media_url.startswith('http'):
                    media_url = 'https://t.me' + media_url
            
            # GIF/анимация
            if not media_url:
                gif_elem = post_elem.select_one('.tgme_widget_message_document_wrap a')
                if gif_elem:
                    media_type = 'animation'
                    media_url = gif_elem.get('href')
                    if media_url and not media_url.startswith('http'):
                        media_url = 'https://t.me' + media_url
            
            if not media_url or not media_type:
                return None
            
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