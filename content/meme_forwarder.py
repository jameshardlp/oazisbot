"""Парсер ID постов с мемами для пересылки."""
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
        "chat_id": "@videos_dolboyoba"  # или числовой ID, если известен
    },
    {
        "name": "shitcollection",
        "url": "https://t.me/shitcollection",
        "chat_id": "@shitcollection"
    },
    {
        "name": "postleftism",
        "url": "https://t.me/postleftism",
        "chat_id": "@postleftism"
    },
    {
        "name": "noviop",
        "url": "https://t.me/noviop",
        "chat_id": "@noviop"
    }
]

class MemeForwarder:
    """Парсер ID постов с мемами для пересылки."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })
        self.sent_cache = set()
        self.posts_cache = []
        self.last_fetch_time = 0
        self.cache_ttl = 3600
    
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
    
    def _extract_post_id(self, post_elem) -> Optional[str]:
        """Извлекает ID поста для пересылки."""
        try:
            # Ищем ссылку на пост
            link = post_elem.select_one('.tgme_widget_message_date a')
            if link:
                href = link.get('href')
                if href:
                    # Извлекаем ID из URL вида: https://t.me/channel/123
                    match = re.search(r'/(\d+)$', href)
                    if match:
                        return match.group(1)
            
            # Альтернативный способ: ищем data-post
            data_post = post_elem.get('data-post')
            if data_post:
                # data-post имеет вид: channel/123
                parts = data_post.split('/')
                if len(parts) == 2:
                    return parts[1]
            
            return None
            
        except Exception as e:
            logger.debug(f"Ошибка извлечения ID: {e}")
            return None
    
    def _has_media(self, post_elem) -> bool:
        """Проверяет, есть ли в посте медиа."""
        try:
            # Проверяем наличие фото, видео, гифки
            media_selectors = [
                '.tgme_widget_message_photo_wrap',
                '.tgme_widget_message_video_wrap',
                '.tgme_widget_message_document_wrap video',
                '.tgme_widget_message_document_wrap .tgme_widget_message_document_icon_video',
                'img[src*="/file/"]',
                'video[src]'
            ]
            
            for selector in media_selectors:
                if post_elem.select_one(selector):
                    return True
            
            # Проверяем, есть ли ссылки на медиа-файлы
            links = post_elem.select('a[href]')
            for link in links:
                href = link.get('href', '')
                if any(ext in href.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.mp4', '.webm']):
                    return True
            
            return False
            
        except Exception as e:
            return False
    
    def get_channel_posts(self, source: Dict, limit: int = 100) -> List[Dict]:
        """Получает ID постов с медиа из канала."""
        logger.info(f"📥 Парсинг {source['name']}...")
        soup = self._fetch_page(source['url'])
        if not soup:
            return []
        
        posts = soup.select('.tgme_widget_message')
        if not posts:
            logger.warning(f"⚠️ Нет постов в {source['name']}")
            return []
        
        result = []
        for post in posts[:limit]:
            if self._has_media(post):
                post_id = self._extract_post_id(post)
                if post_id:
                    result.append({
                        'source_channel': source['chat_id'],
                        'message_id': int(post_id),
                        'source_name': source['name']
                    })
        
        logger.info(f"✅ Найдено {len(result)} постов с медиа в {source['name']}")
        return result
    
    def get_all_posts(self, limit_per_channel: int = 100) -> List[Dict]:
        """Собирает ID постов со всех источников."""
        all_posts = []
        for source in MEME_SOURCES:
            try:
                posts = self.get_channel_posts(source, limit_per_channel)
                all_posts.extend(posts)
                time.sleep(1)
            except Exception as e:
                logger.error(f"❌ Ошибка парсинга {source['name']}: {e}")
        
        random.shuffle(all_posts)
        logger.info(f"📊 Всего собрано {len(all_posts)} постов с мемами")
        return all_posts
    
    def get_random_meme_to_forward(self) -> Optional[Dict]:
        """Возвращает случайный пост для пересылки."""
        if time.time() - self.last_fetch_time > self.cache_ttl or not self.posts_cache:
            logger.info("🔄 Обновление кэша постов с мемами...")
            self.posts_cache = self.get_all_posts(limit_per_channel=100)
            self.last_fetch_time = time.time()
            if len(self.sent_cache) > 500:
                self.sent_cache = set()
        
        # Фильтруем уже отправленные
        available = [p for p in self.posts_cache if p.get('message_id') not in self.sent_cache]
        
        if not available:
            logger.info("🔄 Все посты отправлены, загружаю новые...")
            self.sent_cache = set()
            self.posts_cache = self.get_all_posts(limit_per_channel=100)
            self.last_fetch_time = time.time()
            available = self.posts_cache.copy()
            
            if not available:
                logger.warning("⚠️ Нет доступных постов")
                return None
        
        chosen = random.choice(available)
        self.sent_cache.add(chosen.get('message_id'))
        return chosen

# Глобальный экземпляр
_meme_forwarder = None

def get_random_meme_to_forward() -> Optional[Dict]:
    """Упрощённая функция для получения случайного поста для пересылки."""
    global _meme_forwarder
    if _meme_forwarder is None:
        _meme_forwarder = MemeForwarder()
    return _meme_forwarder.get_random_meme_to_forward()