"""Парсер ID постов с мемами для пересылки."""
import logging
import random
import time
import re
import json
import os
from typing import List, Dict, Optional, Set
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Источники мемов (публичные каналы)
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

# Сколько страниц истории листать на каждый канал
MAX_PAGES_PER_CHANNEL = 10

# Файл для хранения отправленных ID (чтобы не повторяться после перезапуска)
SENT_IDS_FILE = "sent_meme_ids.json"


class MemeForwarder:
    """Парсер ID постов с мемами для пересылки."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        })
        
        # Загружаем отправленные ID с диска
        self.sent_cache: Set[str] = self._load_sent_ids()
        
        self.posts_cache: List[Dict] = []
        self.last_fetch_time = 0
        self.cache_ttl = 3600
    
    def _get_post_key(self, source_name: str, message_id: int) -> str:
        """Уникальный ключ поста: канал + ID."""
        return f"{source_name}:{message_id}"
    
    def _load_sent_ids(self) -> Set[str]:
        """Загружает отправленные ID из файла."""
        try:
            if os.path.exists(SENT_IDS_FILE):
                with open(SENT_IDS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        logger.info(f"📂 Загружено {len(data)} отправленных ID из {SENT_IDS_FILE}")
                        return set(data)
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки {SENT_IDS_FILE}: {e}")
        return set()
    
    def _save_sent_ids(self) -> None:
        """Сохраняет отправленные ID в файл."""
        try:
            with open(SENT_IDS_FILE, 'w', encoding='utf-8') as f:
                json.dump(list(self.sent_cache), f, ensure_ascii=False)
            logger.debug(f"💾 Сохранено {len(self.sent_cache)} отправленных ID")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения {SENT_IDS_FILE}: {e}")
    
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
                match = re.search(r't\.me/[^/]+/(\d+)', href)
                if match:
                    return match.group(1)
            
            return None
            
        except Exception as e:
            logger.debug(f"Ошибка извлечения ID: {e}")
            return None
    
    def _has_media(self, elem) -> bool:
        """Проверяет, есть ли в посте медиа."""
        try:
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
        """Находит все посты на странице."""
        posts = []
        selectors = [
            '.tgme_widget_message',
            '.tgme_widget_message_wrap',
            '[data-post]',
        ]
        
        for selector in selectors:
            found = soup.select(selector)
            if found:
                posts.extend(found)
        
        seen = set()
        unique_posts = []
        for post in posts:
            post_id = self._extract_post_id_from_element(post)
            if post_id and post_id not in seen:
                seen.add(post_id)
                unique_posts.append(post)
        
        return unique_posts
    
    def _get_oldest_post_id(self, soup: BeautifulSoup) -> Optional[str]:
        """Находит ID самого старого поста на странице."""
        try:
            links = soup.find_all('a', href=True)
            post_ids = []
            for link in links:
                href = link.get('href', '')
                match = re.search(r't\.me/[^/]+/(\d+)', href)
                if match:
                    post_ids.append(int(match.group(1)))
            
            if post_ids:
                return str(min(post_ids))
            return None
        except Exception as e:
            logger.debug(f"Ошибка поиска oldest post id: {e}")
            return None
    
    def get_channel_posts(self, source: Dict, limit: int = 200) -> List[Dict]:
        """Получает ID постов с медиа из канала, листая историю вглубь."""
        logger.info(f"📥 Парсинг {source['name']}...")
        
        result = []
        seen_ids: Set[int] = set()
        before_id: Optional[str] = None
        skipped_duplicates = 0
        
        for page in range(MAX_PAGES_PER_CHANNEL):
            url = source['url']
            if before_id:
                url = f"{url}?before={before_id}"
            
            soup = self._fetch_page(url)
            if not soup:
                break
            
            posts = self._find_all_posts(soup)
            if not posts:
                logger.info(f"📄 {source['name']}: страница {page + 1} пустая")
                break
            
            page_oldest_id = self._get_oldest_post_id(soup)
            if not page_oldest_id or page_oldest_id == before_id:
                logger.info(f"📄 {source['name']}: достигнут конец истории")
                break
            
            page_found = 0
            page_skipped = 0
            
            for post in posts:
                if self._has_media(post):
                    post_id = self._extract_post_id_from_element(post)
                    if post_id and int(post_id) not in seen_ids:
                        seen_ids.add(int(post_id))
                        
                        # Проверяем, не отправляли ли уже этот пост
                        post_key = self._get_post_key(source['name'], int(post_id))
                        if post_key in self.sent_cache:
                            page_skipped += 1
                            skipped_duplicates += 1
                            continue
                        
                        result.append({
                            'source_channel': source['chat_id'],
                            'message_id': int(post_id),
                            'source_name': source['name']
                        })
                        page_found += 1
            
            logger.info(
                f"📄 {source['name']}: стр. {page + 1}, "
                f"новых с медиа: {page_found}, "
                f"пропущено (уже отправлено): {page_skipped}, "
                f"всего новых: {len(result)}"
            )
            
            if len(result) >= limit:
                break
            
            before_id = page_oldest_id
            time.sleep(0.5)
        
        logger.info(
            f"✅ {source['name']}: собрано {len(result)} новых постов "
            f"(пропущено дубликатов: {skipped_duplicates})"
        )
        return result
    
    def get_all_posts(self, limit_per_channel: int = 200) -> List[Dict]:
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
        logger.info(f"📊 Всего новых постов с мемами: {len(all_posts)}")
        return all_posts
    
    def get_random_meme_to_forward(self) -> Optional[Dict]:
        """Возвращает случайный пост для пересылки, исключая уже отправленные."""
        # Обновляем кэш, если прошло время
        if time.time() - self.last_fetch_time > self.cache_ttl or not self.posts_cache:
            logger.info("🔄 Обновление кэша постов с мемами...")
            self.posts_cache = self.get_all_posts(limit_per_channel=200)
            self.last_fetch_time = time.time()
        
        # Фильтруем по кэшу отправленных (на случай, если что-то отправилось вне этого цикла)
        available = [
            p for p in self.posts_cache
            if self._get_post_key(p.get('source_name'), p.get('message_id')) not in self.sent_cache
        ]
        
        if not available:
            logger.info("🔄 Все посты из кэша отправлены, загружаю свежие...")
            self.posts_cache = self.get_all_posts(limit_per_channel=200)
            self.last_fetch_time = time.time()
            available = [
                p for p in self.posts_cache
                if self._get_post_key(p.get('source_name'), p.get('message_id')) not in self.sent_cache
            ]
            
            if not available:
                logger.warning("⚠️ Нет доступных постов (все уже отправлены)")
                return None
        
        chosen = random.choice(available)
        post_key = self._get_post_key(chosen.get('source_name'), chosen.get('message_id'))
        self.sent_cache.add(post_key)
        
        # Сохраняем на диск, чтобы после перезапуска не повторяться
        self._save_sent_ids()
        
        logger.info(
            f"🎯 Выбран пост: {post_key} "
            f"(осталось неопубликованных: {len(available) - 1}, "
            f"всего в базе: {len(self.sent_cache)})"
        )
        return chosen


# Глобальный экземпляр
_meme_forwarder = None


def get_random_meme_to_forward() -> Optional[Dict]:
    """Упрощённая функция для получения случайного поста для пересылки."""
    global _meme_forwarder
    if _meme_forwarder is None:
        _meme_forwarder = MemeForwarder()
    return _meme_forwarder.get_random_meme_to_forward()
