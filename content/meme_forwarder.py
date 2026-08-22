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
        "chat_id": "@videos_dolboyoba"
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
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
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
                # Сохраняем HTML для отладки
                with open(f"debug_{url.split('/')[-1]}.html", "w", encoding="utf-8") as f:
                    f.write(response.text)
                return BeautifulSoup(response.text, 'html.parser')
            logger.warning(f"Ошибка загрузки {url}: {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Ошибка загрузки {url}: {e}")
            return None
    
    def _extract_post_id_from_element(self, elem) -> Optional[str]:
        """Универсальное извлечение ID поста из любого элемента."""
        try:
            # 1. Ищем data-post
            data_post = elem.get('data-post')
            if data_post:
                parts = data_post.split('/')
                if len(parts) == 2:
                    return parts[1]
            
            # 2. Ищем ссылку .tgme_widget_message_date a
            link = elem.select_one('.tgme_widget_message_date a')
            if link:
                href = link.get('href')
                if href:
                    match = re.search(r'/(\d+)$', href)
                    if match:
                        return match.group(1)
            
            # 3. Ищем любую ссылку, содержащую t.me/канал/цифры
            links = elem.find_all('a', href=True)
            for link in links:
                href = link.get('href', '')
                # Ищем паттерн: t.me/название/число
                match = re.search(r't\.me/[^/]+/(\d+)', href)
                if match:
                    return match.group(1)
            
            return None
            
        except Exception as e:
            logger.debug(f"Ошибка извлечения ID: {e}")
            return None
    
    def _has_media(self, elem) -> bool:
        """Проверяет, есть ли в посте медиа (универсально)."""
        try:
            # Проверяем наличие медиа-элементов
            media_selectors = [
                '.tgme_widget_message_photo_wrap',
                '.tgme_widget_message_video_wrap',
                '.tgme_widget_message_document_wrap',
                'img[src*="/file/"]',
                'img[src*=".jpg"]',
                'img[src*=".png"]',
                'img[src*=".gif"]',
                'video[src]',
                '.tgme_widget_message_document_icon_video',
            ]
            
            for selector in media_selectors:
                if elem.select_one(selector):
                    return True
            
            # Проверяем ссылки на медиа-файлы
            links = elem.find_all('a', href=True)
            for link in links:
                href = link.get('href', '').lower()
                if any(ext in href for ext in ['.jpg', '.jpeg', '.png', '.gif', '.mp4', '.webm', '.webp']):
                    return True
                if '/file/' in href:
                    return True
            
            return False
            
        except Exception as e:
            return False
    
    def _find_all_posts(self, soup: BeautifulSoup) -> List:
        """Находит все посты на странице (универсально)."""
        posts = []
        
        # Пробуем разные селекторы
        selectors = [
            '.tgme_widget_message',
            '.tgme_widget_message_wrap',
            '.tgme_widget_message_text',
            '[data-post]',
            '.message',
            '.post',
            '.media',
        ]
        
        for selector in selectors:
            found = soup.select(selector)
            if found:
                posts.extend(found)
                logger.debug(f"Найдено {len(found)} элементов по селектору: {selector}")
                # Не прерываем, собираем все возможные
        
        # Если ничего не нашли — ищем любые div с атрибутами
        if not posts:
            all_divs = soup.find_all('div')
            for div in all_divs:
                if div.get('data-post') or div.get('class') and any('message' in str(c) for c in div.get('class', [])):
                    posts.append(div)
        
        # Убираем дубликаты по data-post или содержимому
        seen = set()
        unique_posts = []
        for post in posts:
            post_id = self._extract_post_id_from_element(post)
            if post_id and post_id not in seen:
                seen.add(post_id)
                unique_posts.append(post)
            elif not post_id:
                # Если нет ID, добавляем по содержимому (меньше дубликатов)
                content = str(post)[:200]
                if content not in seen:
                    seen.add(content)
                    unique_posts.append(post)
        
        return unique_posts
    
    def get_channel_posts(self, source: Dict, limit: int = 100) -> List[Dict]:
        """Получает ID постов с медиа из канала."""
        logger.info(f"📥 Парсинг {source['name']}...")
        soup = self._fetch_page(source['url'])
        if not soup:
            logger.warning(f"⚠️ Не удалось загрузить {source['name']}")
            return []
        
        # Сохраняем HTML для отладки
        with open(f"debug_{source['name']}_soup.html", "w", encoding="utf-8") as f:
            f.write(str(soup)[:50000])
        
        posts = self._find_all_posts(soup)
        
        if not posts:
            logger.warning(f"⚠️ Нет постов в {source['name']}")
            return []
        
        logger.info(f"📊 Найдено {len(posts)} потенциальных постов в {source['name']}")
        
        result = []
        for post in posts[:limit]:
            if self._has_media(post):
                post_id = self._extract_post_id_from_element(post)
                if post_id:
                    result.append({
                        'source_channel': source['chat_id'],
                        'message_id': int(post_id),
                        'source_name': source['name']
                    })
        
        logger.info(f"✅ Найдено {len(result)} постов с медиа в {source['name']}")
        
        # Если не найдено, пробуем альтернативный подход
        if not result:
            logger.info(f"🔄 Пробую альтернативный парсинг для {source['name']}...")
            # Ищем все ссылки на посты
            links = soup.find_all('a', href=True)
            for link in links:
                href = link.get('href', '')
                if 't.me' in href:
                    match = re.search(r't\.me/[^/]+/(\d+)', href)
                    if match:
                        post_id = match.group(1)
                        # Проверяем, есть ли рядом медиа
                        parent = link.parent
                        if parent and self._has_media(parent):
                            result.append({
                                'source_channel': source['chat_id'],
                                'message_id': int(post_id),
                                'source_name': source['name']
                            })
            
            # Убираем дубликаты
            seen = set()
            unique_result = []
            for item in result:
                if item['message_id'] not in seen:
                    seen.add(item['message_id'])
                    unique_result.append(item)
            result = unique_result
            logger.info(f"✅ Альтернативный парсинг: найдено {len(result)} постов")
        
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
            self.posts_cache = self.get_all_posts(limit_per_channel=50)  # Берём 50 для скорости
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
        return chosen

# Глобальный экземпляр
_meme_forwarder = None

def get_random_meme_to_forward() -> Optional[Dict]:
    """Упрощённая функция для получения случайного поста для пересылки."""
    global _meme_forwarder
    if _meme_forwarder is None:
        _meme_forwarder = MemeForwarder()
    return _meme_forwarder.get_random_meme_to_forward()
