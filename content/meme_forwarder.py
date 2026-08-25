"""Парсер ID постов с мемами для пересылки.

Список каналов-источников живёт в settings.py и правится командой /sources,
поэтому читается на каждый обход, а не фиксируется константой при импорте.
"""
import logging
import random
import time
from typing import List, Dict, Optional

from bs4 import BeautifulSoup

import settings
from content import net

logger = logging.getLogger(__name__)


def get_meme_sources() -> List[Dict]:
    """Каналы-источники в том виде, в каком их ждёт get_channel_posts."""
    return [
        {
            "name": name,
            "url": f"https://t.me/s/{name}",
            "chat_id": f"@{name}",
        }
        for name in settings.get_meme_channels()
    ]


class MemeForwarder:
    def __init__(self):
        # Своя сессия (t.me ставит свои cookies), заголовки и ретраи — общие
        self.session = net.new_session()
        self.sent_cache = set()
        self.posts_cache = []
        self.last_fetch_time = 0
        self.cache_ttl = 3600

    def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        response = net.request(
            "GET", url, session=self.session, label=f"мемы {url}",
        )
        if response is None or response.status_code != 200:
            if response is not None:
                logger.warning(f"⚠️ {url}: HTTP {response.status_code}")
            return None
        return BeautifulSoup(response.text, 'html.parser')

    def get_channel_posts(self, source: Dict, limit: int = 100) -> List[Dict]:
        """Получает реальные ID постов с медиа из канала."""
        logger.info(f"📥 Парсинг {source['name']}...")
        soup = self._fetch_page(source['url'])
        if not soup:
            return []
        return self._extract_posts(soup, source, limit)

    def _extract_posts(self, soup: BeautifulSoup, source: Dict, limit: int) -> List[Dict]:
        """Разбор уже загруженной страницы. Отделён от загрузки, чтобы check_channel
        мог различить «канал недоступен» и «в канале нет медиа»."""
        # Ищем все посты
        posts = soup.select('.tgme_widget_message')
        if not posts:
            net.log_layout_changed(
                f"мемы {source['name']}", source['url'],
                "нет ни одного .tgme_widget_message",
            )
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

        if not result:
            # Посты есть, а медиа-обёрток нет ни у одного — это уже про вёрстку,
            # а не про «в канале только текст»
            net.log_layout_changed(
                f"мемы {source['name']}", source['url'],
                f"постов найдено {len(posts)}, но ни у одного нет "
                "*_photo_wrap / *_video_wrap / *_document_wrap",
            )
            return []

        logger.info(f"✅ Найдено {len(result)} постов с медиа в {source['name']}")
        return result
    
    def get_all_posts(self, limit_per_channel: int = 100) -> List[Dict]:
        sources = get_meme_sources()
        if not sources:
            logger.warning(
                "⚠️ Список каналов-источников пуст — брать мемы неоткуда. "
                "Добавь канал командой /sources add"
            )
            return []

        all_posts = []
        for source in sources:
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

def _get_forwarder() -> MemeForwarder:
    """Один экземпляр на процесс: в нём живут сессия и кэш отправленных постов."""
    global _meme_forwarder
    if _meme_forwarder is None:
        _meme_forwarder = MemeForwarder()
    return _meme_forwarder

def get_random_meme_to_forward() -> Optional[Dict]:
    return _get_forwarder().get_random_meme_to_forward()

def invalidate_cache() -> None:
    """Сбрасывает кэш постов, чтобы правки /sources подействовали сразу.

    sent_cache намеренно не трогаем: иначе после каждой правки списка в канал
    поехали бы уже отправленные мемы.
    """
    forwarder = _get_forwarder()
    forwarder.posts_cache = []
    forwarder.last_fetch_time = 0
    logger.info("🔄 Кэш постов сброшен — список каналов изменился")

def check_channel(name: str) -> Optional[int]:
    """Сколько постов с медиа видно в канале. None — страницу прочитать не удалось.

    Нужна команде /sources add, чтобы сразу сказать, будет ли с канала толк.

    Работает на своём экземпляре, а не на синглтоне: проверка идёт из потока
    хендлера, планировщик в это же время может парсить каналы в своём, а
    requests.Session между потоками делить нельзя.

    Страницу запрашиваем отдельно от разбора: get_channel_posts отдаёт пустой
    список и когда канал недоступен, и когда в нём просто нет медиа, а для
    ответа админу это две разные новости.
    """
    checker = MemeForwarder()
    url = f"https://t.me/s/{name}"
    source = {"name": name, "url": url, "chat_id": f"@{name}"}
    try:
        soup = checker._fetch_page(url)
        if soup is None:
            return None
        return len(checker._extract_posts(soup, source, limit=20))
    except Exception as e:
        logger.error(f"❌ Не удалось проверить канал {name}: {e}")
        return None
