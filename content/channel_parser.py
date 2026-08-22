"""Парсер постов из публичного Telegram канала через веб-интерфейс.

Не требует API ключей, работает с публичными каналами через t.me/s/{username}.
Использует встроенный html.parser (не требует установки bs4).
"""
import logging
import time
import re
from typing import List, Optional, Dict, Any
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
REQUEST_TIMEOUT = 15
MAX_RETRIES = 3
RETRY_DELAY = 2


class TelegramHTMLParser(HTMLParser):
    """Простой HTML парсер для извлечения сообщений из Telegram канала."""
    
    def __init__(self):
        super().__init__()
        self.messages = []
        self.current_message = None
        self.current_tag = None
        self.in_message = False
        self.in_text = False
        self.text_buffer = []
        self.date_buffer = []
        self.views_buffer = []
        self.in_date = False
        self.in_views = False
        self.in_link = False
        self.link_buffer = []
        
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        
        # Поиск сообщения по классу
        if tag == 'div' and 'class' in attrs_dict:
            classes = attrs_dict['class'].split()
            if 'tgme_widget_message' in classes:
                self.in_message = True
                self.current_message = {'text': '', 'date': '', 'views': '', 'link': ''}
                self.text_buffer = []
                self.date_buffer = []
                self.views_buffer = []
                self.link_buffer = []
        
        # Текст сообщения
        if self.in_message and tag == 'div' and 'class' in attrs_dict:
            if 'tgme_widget_message_text' in attrs_dict['class'].split():
                self.in_text = True
        
        # Дата
        if self.in_message and tag == 'time' and 'class' in attrs_dict:
            if 'tgme_widget_message_date' in attrs_dict['class'].split():
                self.in_date = True
                if 'datetime' in attrs_dict:
                    self.current_message['date'] = attrs_dict['datetime']
        
        # Ссылка
        if self.in_message and tag == 'a' and 'class' in attrs_dict:
            if 'tgme_widget_message_date' in attrs_dict['class'].split():
                self.in_link = True
                if 'href' in attrs_dict:
                    self.current_message['link'] = attrs_dict['href']
        
        # Просмотры
        if self.in_message and tag == 'span' and 'class' in attrs_dict:
            if 'tgme_widget_message_views' in attrs_dict['class'].split():
                self.in_views = True
    
    def handle_endtag(self, tag):
        if tag == 'div' and self.in_message:
            # Проверяем, что у нас есть текст
            if self.current_message and self.current_message.get('text', '').strip():
                # Сохраняем сообщение
                self.current_message['text'] = ''.join(self.text_buffer).strip()
                if self.current_message['text'] and len(self.current_message['text']) > 10:
                    self.messages.append(self.current_message.copy())
            
            self.in_message = False
            self.current_message = None
            self.text_buffer = []
            self.date_buffer = []
            self.views_buffer = []
            self.link_buffer = []
            self.in_text = False
            self.in_date = False
            self.in_views = False
            self.in_link = False
    
    def handle_data(self, data):
        if self.in_text and self.in_message:
            self.text_buffer.append(data)
        if self.in_date and self.in_message:
            self.date_buffer.append(data)
        if self.in_views and self.in_message:
            self.views_buffer.append(data)
        if self.in_link and self.in_message:
            self.link_buffer.append(data)


def get_channel_posts(username: str = "maddysontg", limit: int = 5) -> List[str]:
    """
    Получает посты из публичного канала через простой HTML парсер.
    
    Args:
        username: Имя канала без @
        limit: Количество постов
        
    Returns:
        Список текстов постов
    """
    logger.info(f"📖 Читаю посты из канала {username} (лимит: {limit})...")
    
    url = f"https://t.me/s/{username}"
    
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(
                url,
                headers={'User-Agent': USER_AGENT},
                timeout=REQUEST_TIMEOUT
            )
            
            if response.status_code == 200:
                # Используем встроенный парсер
                parser = TelegramHTMLParser()
                parser.feed(response.text)
                
                posts = []
                for msg in parser.messages[:limit]:
                    text = msg.get('text', '').strip()
                    if text and len(text) > 10:
                        posts.append(text)
                        if len(posts) >= limit:
                            break
                
                logger.info(f"✅ Получено {len(posts)} постов из канала {username}")
                return posts
                
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
            logger.error(f"Ошибка при загрузке: {e}")
            time.sleep(RETRY_DELAY)
            continue
    
    logger.warning(f"⚠️ Не удалось получить посты из канала {username}")
    return []


def get_default_style_examples() -> List[str]:
    """Возвращает примеры стиля на случай, если канал недоступен."""
    return [
        "Да ну нахуй, этот клоун опять на стриме орёт. Сидел бы лучше в МЧС, чем зрителей за деньги веселить.",
        "Смотрю я на этого блогера и думаю — ну как так можно жить? Накрутил ботов и думает что он король.",
        "Азия — это пиздец. Там такое творится, что я ахерел. Люди живут в каком-то параллельном мире.",
        "Дианочка снова накрутила. Сколько можно? У меня уже крыша едет от этой ботоводки.",
    ]


# Глобальный кэш
_cached_posts = []
_cache_time = 0
CACHE_TTL = 3600


def get_posts_from_channel_web(limit: int = 5, force_refresh: bool = False) -> List[str]:
    """Получает посты из канала через веб-парсер с кэшированием."""
    global _cached_posts, _cache_time
    
    current_time = time.time()
    
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
