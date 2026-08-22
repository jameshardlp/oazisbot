# content/meme_parser.py (исправленная версия с отладкой)
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
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })
        self.sent_cache = set()
        self.media_cache = []
        self.last_fetch_time = 0
        self.cache_ttl = 3600
    
    def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Загружает страницу канала."""
        try:
            response = self.session.get(url, timeout=15)
            if response.status_code == 200:
                # Сохраняем HTML для отладки
                if logger.isEnabledFor(logging.DEBUG):
                    with open(f"debug_{url.split('/')[-1]}.html", "w", encoding="utf-8") as f:
                        f.write(response.text[:5000])
                return BeautifulSoup(response.text, 'html.parser')
            logger.warning(f"Ошибка загрузки {url}: {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Ошибка загрузки {url}: {e}")
            return None
    
    def _extract_media_from_post(self, post) -> List[Dict]:
        """Извлекает все медиа из одного поста."""
        results = []
        
        try:
            # 1. Ищем ВСЕ изображения
            images = post.find_all('img')
            for img in images:
                src = img.get('src')
                if src:
                    # Получаем полный URL
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/'):
                        src = 'https://t.me' + src
                    
                    # Проверяем, что это не иконка и не аватарка
                    if 'emoji' in src or 'avatar' in src or 'logo' in src:
                        continue
                    
                    # Проверяем расширение
                    if any(src.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                        results.append({
                            'media_url': src,
                            'media_type': 'photo',
                            'source': 'telegram'
                        })
                        continue
                    
                    # Если это превью — преобразуем
                    if '/preview/' in src:
                        src_full = src.replace('/preview/', '/file/')
                        results.append({
                            'media_url': src_full,
                            'media_type': 'photo',
                            'source': 'telegram'
                        })
            
            # 2. Ищем ВИДЕО
            videos = post.find_all('video')
            for video in videos:
                src = video.get('src')
                if src:
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/'):
                        src = 'https://t.me' + src
                    
                    if any(src.lower().endswith(ext) for ext in ['.mp4', '.webm', '.mov']):
                        results.append({
                            'media_url': src,
                            'media_type': 'video',
                            'source': 'telegram'
                        })
            
            # 3. Ищем ссылки на файлы (GIF, документы)
            links = post.find_all('a', href=True)
            for link in links:
                href = link.get('href')
                if href:
                    if href.startswith('//'):
                        href = 'https:' + href
                    elif href.startswith('/'):
                        href = 'https://t.me' + href
                    
                    # Проверяем расширения
                    if any(href.lower().endswith(ext) for ext in ['.gif', '.mp4', '.webm', '.webp']):
                        results.append({
                            'media_url': href,
                            'media_type': 'animation',
                            'source': 'telegram'
                        })
                    
                    # Проверяем ссылки на Telegram файлы
                    if '/file/' in href:
                        results.append({
                            'media_url': href,
                            'media_type': 'file',
                            'source': 'telegram'
                        })
        
        except Exception as e:
            logger.debug(f"Ошибка извлечения медиа: {e}")
        
        return results
    
    def get_channel_media(self, source: Dict, limit: int = 100) -> List[Dict]:
        """Получает медиа из канала."""
        logger.info(f"📥 Парсинг {source['name']}...")
        soup = self._fetch_page(source['url'])
        if not soup:
            logger.warning(f"⚠️ Не удалось загрузить {source['name']}")
            return []
        
        # Пробуем разные селекторы для постов
        posts = soup.select('.tgme_widget_message')
        if not posts:
            # Альтернативные селекторы
            posts = soup.select('.tgme_widget_message_wrap')
        if not posts:
            posts = soup.select('.tgme_widget_message_text')  # Может быть только текст
        
        if not posts:
            logger.warning(f"⚠️ Нет постов в {source['name']}")
            # Сохраняем HTML для отладки
            with open(f"debug_{source['name']}_no_posts.html", "w", encoding="utf-8") as f:
                f.write(str(soup)[:10000])
            return []
        
        logger.info(f"📊 Найдено {len(posts)} постов в {source['name']}")
        
        all_media = []
        for post in posts[:limit]:
            media_items = self._extract_media_from_post(post)
            if media_items:
                all_media.extend(media_items)
                logger.debug(f"Найдено {len(media_items)} медиа в посте")
        
        # Убираем дубликаты
        seen = set()
        unique_media = []
        for item in all_media:
            url = item.get('media_url')
            if url and url not in seen:
                seen.add(url)
                unique_media.append(item)
        
        logger.info(f"✅ Найдено {len(unique_media)} уникальных медиа в {source['name']}")
        
        # Показываем пример
        if unique_media:
            logger.info(f"   Пример: {unique_media[0]['media_url'][:80]}...")
        
        return unique_media
    
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
        """Возвращает случайный мем."""
        if time.time() - self.last_fetch_time > self.cache_ttl or not self.media_cache:
            logger.info("🔄 Обновление кэша мемов...")
            self.media_cache = self.get_all_media(limit_per_channel=100)
            self.last_fetch_time = time.time()
            if len(self.sent_cache) > 500:
                self.sent_cache = set()
        
        available = [m for m in self.media_cache if m.get('media_url') not in self.sent_cache]
        
        if not available:
            logger.info("🔄 Все мемы отправлены, загружаю новые...")
            self.sent_cache = set()
            self.media_cache = self.get_all_media(limit_per_channel=100)
            self.last_fetch_time = time.time()
            available = self.media_cache.copy()
            
            if not available:
                logger.warning("⚠️ Нет доступных мемов")
                return None
        
        chosen = random.choice(available)
        self.sent_cache.add(chosen.get('media_url'))
        
        return chosen

# Глобальный экземпляр
_meme_parser = None

def get_random_meme() -> Optional[Dict]:
    """Упрощённая функция для получения случайного мема."""
    global _meme_parser
    if _meme_parser is None:
        _meme_parser = MemeParser()
    return _meme_parser.get_random_meme()
