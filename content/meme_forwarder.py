"""Парсер ID постов с мемами для пересылки."""
import logging
import random
import time
import re
from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

MEME_SOURCES = [
    {
        "name": "videos_dolboyoba",
        "url": "https://t.me/s/videos_dolboyoba",
        "chat_id": "@videos_dolboyoba"
    },
    {
        "name": "shitcollection",
        "url": "https://t.me/s/shitcollection",
        "chat_id": "@shitcollection"
    },
    {
        "name": "postleftism",
        "url": "https://t.me/s/postleftism",
        "chat_id": "@postleftism"
    },
    {
        "name": "noviop",
        "url": "https://t.me/s/noviop",
        "chat_id": "@noviop"
    }
]

class MemeForwarder:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        })
        self.sent_cache = set()
        self.posts_cache = []
        self.last_fetch_time = 0
        self.cache_ttl = 3600
    
    def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        try:
            response = self.session.get(url, timeout=15)
            if response.status_code == 200:
                return BeautifulSoup(response.text, 'html.parser')
            return None
        except Exception as e:
            logger.error(f"Ошибка загрузки {url}: {e}")
            return None
    
    def get_channel_posts(self, source: Dict, limit: int = 100) -> List[Dict]:
        """Получает реальные ID постов с медиа из канала."""
        logger.info(f"📥 Парсинг {source['name']}...")
        soup = self._fetch_page(source['url'])
        if not soup:
            return []
        
        # Ищем все посты
        posts = soup.select('.tgme_widget_message')
        if not posts:
            logger.warning(f"⚠️ Нет постов в {source['name']}")
            return []
        
        logger.info(f"📊 Найдено {len(posts)} постов в {source['name']}")
        
        result = []
        for post in posts[:limit]:
            # Проверяем наличие медиа
            has_media = post.select_one('.tgme_widget_message_photo_wrap, .tgme_widget_message_video_wrap, .tgme_widget_message_document_wrap')
            if not has_media:
                continue
            
            # Получаем РЕАЛЬНЫЙ ID сообщения из data-post
            data_post = post.get('data-post')
            if not data_post:
                continue
            
            # data-post имеет формат: "channel_name/message_id"
            parts = data_post.split('/')
            if len(parts) != 2:
                continue
            
            real_message_id = parts[1]  # Это реальный ID для API
            
            result.append({
                'source_channel': source['chat_id'],
                'message_id': int(real_message_id),
                'source_name': source['name'],
                'web_id': parts[0]  # Для информации
            })
            logger.debug(f"  Найден пост: data-post={data_post}")
        
        logger.info(f"✅ Найдено {len(result)} постов с медиа в {source['name']}")
        return result
    
    def get_all_posts(self, limit_per_channel: int = 100) -> List[Dict]:
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
        if time.time() - self.last_fetch_time > self.cache_ttl or not self.posts_cache:
            logger.info("🔄 Обновление кэша постов с мемами...")
            self.posts_cache = self.get_all_posts(limit_per_channel=50)
            self.last_fetch_time = time.time()
            if len(self.sent_cache) > 500:
                self.sent_cache = set()
        
        available = [p for p in self.posts_cache if p.get('message_id') not in self.sent_cache]
        
        if not available:
            logger.info("🔄 Все посты отправлены, загружаю новые...")
            self.sent_cache = set()
            self.posts_cache = self.get_all_posts(limit_per_channel=50)
            self.last_fetch_time = time.time()
            available = self.posts_cache.copy()
            
            if not available:
                logger.warning("⚠️ Нет доступных постов")
                return None
        
        chosen = random.choice(available)
        self.sent_cache.add(chosen.get('message_id'))
        logger.info(f"🎯 Выбран пост: {chosen.get('source_name')} / {chosen.get('message_id')}")
        return chosen

_meme_forwarder = None

def get_random_meme_to_forward() -> Optional[Dict]:
    global _meme_forwarder
    if _meme_forwarder is None:
        _meme_forwarder = MemeForwarder()
    return _meme_forwarder.get_random_meme_to_forward()
