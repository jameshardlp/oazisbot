"""Парсер постов из публичного Telegram канала через веб-интерфейс.

Не требует API ключей, работает с публичными каналами через t.me/s/{username}.
Использует BeautifulSoup для парсинга HTML.
"""
import logging
import time
import re
from typing import List, Optional, Dict, Any
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Настройки парсера
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
REQUEST_TIMEOUT = 15
MAX_RETRIES = 3
RETRY_DELAY = 2

class TelegramChannelParser:
    """Парсер публичных Telegram каналов."""
    
    def __init__(self, username: str):
        """
        Инициализация парсера для конкретного канала.
        
        Args:
            username: Имя канала без @ (например, "maddysontg")
        """
        self.username = username.strip('@')
        self.base_url = f"https://t.me/s/{self.username}"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
    def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """
        Загружает страницу и возвращает BeautifulSoup объект.
        
        Args:
            url: URL страницы для загрузки
            
        Returns:
            BeautifulSoup объект или None при ошибке
        """
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.get(
                    url,
                    timeout=REQUEST_TIMEOUT,
                    allow_redirects=True
                )
                
                if response.status_code == 200:
                    # Проверяем, что это HTML, а не JSON или что-то ещё
                    content_type = response.headers.get('Content-Type', '')
                    if 'text/html' in content_type or response.text.strip().startswith('<!DOCTYPE'):
                        return BeautifulSoup(response.text, 'lxml')
                    else:
                        logger.warning(f"Не HTML ответ: {content_type}")
                        return None
                elif response.status_code == 429:
                    # Слишком много запросов
                    wait_time = RETRY_DELAY * (attempt + 1)
                    logger.warning(f"Rate limit, ждём {wait_time} секунд...")
                    time.sleep(wait_time)
                    continue
                elif response.status_code == 404:
                    logger.error(f"Канал {self.username} не найден или недоступен")
                    return None
                else:
                    logger.warning(f"Ошибка HTTP {response.status_code} (попытка {attempt + 1})")
                    time.sleep(RETRY_DELAY)
                    continue
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Таймаут при загрузке (попытка {attempt + 1})")
                time.sleep(RETRY_DELAY)
                continue
            except requests.exceptions.ConnectionError:
                logger.warning(f"Ошибка соединения (попытка {attempt + 1})")
                time.sleep(RETRY_DELAY)
                continue
            except Exception as e:
                logger.error(f"Ошибка при загрузке страницы: {e}")
                time.sleep(RETRY_DELAY)
                continue
        
        return None
    
    def _parse_message(self, message_elem) -> Optional[Dict[str, Any]]:
        """
        Парсит одно сообщение из элемента BeautifulSoup.
        
        Args:
            message_elem: BeautifulSoup элемент сообщения
            
        Returns:
            Словарь с данными сообщения или None
        """
        try:
            # Текст сообщения
            text_elem = message_elem.select_one('.tgme_widget_message_text')
            if not text_elem:
                return None
            
            text = text_elem.get_text(strip=True)
            if not text or len(text) < 10:
                return None
            
            # Дата/время
            date_elem = message_elem.select_one('.tgme_widget_message_date time')
            date_str = None
            timestamp = None
            if date_elem:
                date_str = date_elem.get('datetime')
                if date_str:
                    try:
                        # Парсим ISO формат: 2024-01-15T10:30:00+00:00
                        timestamp = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    except:
                        pass
            
            # Просмотры
            views_elem = message_elem.select_one('.tgme_widget_message_views')
            views = None
            if views_elem:
                views_text = views_elem.get_text(strip=True)
                if views_text:
                    try:
                        views = int(re.sub(r'[^\d]', '', views_text))
                    except:
                        pass
            
            # Ссылка на сообщение (для получения permalink)
            link_elem = message_elem.select_one('.tgme_widget_message_date a')
            link = None
            if link_elem:
                link = link_elem.get('href')
            
            return {
                'text': text,
                'date': date_str,
                'timestamp': timestamp,
                'views': views,
                'link': link,
                'raw': str(message_elem)[:200]  # для отладки
            }
            
        except Exception as e:
            logger.debug(f"Ошибка при парсинге сообщения: {e}")
            return None
    
    def get_posts(self, limit: int = 10, before: Optional[str] = None) -> List[str]:
        """
        Получает тексты постов из канала.
        
        Args:
            limit: Максимальное количество постов
            before: Опционально, ID предыдущего сообщения для пагинации
            
        Returns:
            Список текстов постов
        """
        logger.info(f"📖 Читаю посты из канала {self.username} (лимит: {limit})...")
        
        # Формируем URL
        url = self.base_url
        if before:
            url = f"{url}?before={before}"
        
        # Загружаем страницу
        soup = self._fetch_page(url)
        if not soup:
            logger.error(f"❌ Не удалось загрузить страницу канала {self.username}")
            return []
        
        # Находим все сообщения
        messages = soup.select('.tgme_widget_message')
        
        if not messages:
            logger.warning(f"⚠️ Сообщения не найдены. Возможно, канал приватный или изменилась вёрстка.")
            # Попробуем альтернативные селекторы
            messages = soup.select('.tgme_widget_message_wrap')
        
        posts = []
        for msg in messages[:limit]:
            parsed = self._parse_message(msg)
            if parsed and parsed['text']:
                posts.append(parsed['text'])
                
                # Если набрали нужное количество
                if len(posts) >= limit:
                    break
        
        logger.info(f"✅ Получено {len(posts)} постов из канала {self.username}")
        return posts
    
    def get_posts_with_metadata(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Получает посты с полной метаинформацией.
        
        Args:
            limit: Максимальное количество постов
            
        Returns:
            Список словарей с данными постов
        """
        logger.info(f"📖 Читаю посты с метаданными из канала {self.username} (лимит: {limit})...")
        
        soup = self._fetch_page(self.base_url)
        if not soup:
            return []
        
        messages = soup.select('.tgme_widget_message')
        posts = []
        
        for msg in messages[:limit]:
            parsed = self._parse_message(msg)
            if parsed and parsed['text']:
                posts.append(parsed)
                if len(posts) >= limit:
                    break
        
        logger.info(f"✅ Получено {len(posts)} постов с метаданными")
        return posts


# ===== УПРОЩЁННЫЙ ИНТЕРФЕЙС =====

def get_channel_posts(username: str = "maddysontg", limit: int = 5) -> List[str]:
    """
    Простая функция для получения постов из публичного канала.
    
    Args:
        username: Имя канала без @
        limit: Количество постов
        
    Returns:
        Список текстов постов
    """
    parser = TelegramChannelParser(username)
    return parser.get_posts(limit=limit)


# ===== АДАПТЕР ДЛЯ ИНТЕГРАЦИИ С СУЩЕСТВУЮЩИМ КОДОМ =====

# Глобальный кэш для постов из канала
_cached_posts = []
_cache_time = 0
CACHE_TTL = 3600  # Обновлять раз в час

def get_posts_from_channel_web(limit: int = 5, force_refresh: bool = False) -> List[str]:
    """
    Получает посты из канала через веб-парсер с кэшированием.
    Заменяет Pyrogram версию.
    
    Args:
        limit: Количество постов
        force_refresh: Принудительно обновить кэш
        
    Returns:
        Список текстов постов
    """
    global _cached_posts, _cache_time
    
    current_time = time.time()
    
    # Если кэш ещё свежий — возвращаем его
    if not force_refresh and _cached_posts and (current_time - _cache_time) < CACHE_TTL:
        logger.info(f"📦 Использую кэш веб-парсера ({len(_cached_posts)} постов)")
        return _cached_posts
    
    try:
        posts = get_channel_posts("maddysontg", limit=limit)
        
        if posts:
            _cached_posts = posts
            _cache_time = current_time
            logger.info(f"✅ Загружено {len(posts)} постов через веб-парсер")
            return posts
        else:
            logger.warning("⚠️ Не удалось загрузить посты через веб-парсер, использую заглушку")
            posts = get_default_style_examples()
            _cached_posts = posts
            _cache_time = current_time
            return posts
            
    except Exception as e:
        logger.error(f"❌ Ошибка при получении постов через веб-парсер: {e}")
        posts = get_default_style_examples()
        _cached_posts = posts
        _cache_time = current_time
        return posts


def get_default_style_examples() -> List[str]:
    """Возвращает примеры стиля на случай, если канал недоступен."""
    return [
        "Да ну нахуй, этот клоун опять на стриме орёт. Сидел бы лучше в МЧС, чем зрителей за деньги веселить.",
        "Смотрю я на этого блогера и думаю — ну как так можно жить? Накрутил ботов и думает что он король.",
        "Азия — это пиздец. Там такое творится, что я ахерел. Люди живут в каком-то параллельном мире.",
        "Дианочка снова накрутила. Сколько можно? У меня уже крыша едет от этой ботоводки.",
    ]


# ===== ТЕСТИРОВАНИЕ =====
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    print("\n" + "="*60)
    print("🧪 ТЕСТИРОВАНИЕ ПАРСЕРА КАНАЛА")
    print("="*60 + "\n")
    
    # Тест 1: Получение постов
    print("📖 Получение постов из канала maddysontg...")
    posts = get_channel_posts("maddysontg", limit=3)
    
    if posts:
        print(f"\n✅ Получено {len(posts)} постов:\n")
        for i, post in enumerate(posts, 1):
            print(f"--- Пост {i} ---")
            print(post)
            print()
    else:
        print("❌ Не удалось получить посты")
    
    # Тест 2: Получение с метаданными
    print("\n" + "="*60)
    print("📊 Получение постов с метаданными...")
    parser = TelegramChannelParser("maddysontg")
    posts_meta = parser.get_posts_with_metadata(limit=2)
    
    if posts_meta:
        for post in posts_meta:
            print(f"\n📝 Текст: {post['text'][:100]}...")
            print(f"📅 Дата: {post['date']}")
            print(f"👁️ Просмотры: {post['views']}")
            if post.get('link'):
                print(f"🔗 Ссылка: {post['link']}")
    else:
        print("❌ Не удалось получить метаданные")