"""Парсер постов с мемами: ID сообщений и прямые ссылки на медиа.

Список каналов-источников живёт в settings.py и правится командой /sources,
поэтому читается на каждый обход, а не фиксируется константой при импорте.

Ссылки на медиа вынимаются здесь же, из уже загруженной страницы t.me/s/<канал>:
в ней и `<video src>`, и обёртки фото со `background-image`. Раньше этим занимался
meme_scheduler — он лез на страницу одиночного поста t.me/<канал>/<id>, где ни
mp4, ни всех фото альбома вообще нет, только og:image-превью первого кадра.
Из-за этого видео не публиковались никогда, а из альбома уходило одно фото.

Что уже публиковалось, помнит content/posted_store: посты оттуда в кандидаты не
попадают вообще. Когда на первой странице канала новых постов не осталось,
подгружаем историю глубже (t.me/s/<канал>?before=<id>) — иначе бот замолчал бы
через несколько дней, исчерпав видимые ~20 постов.
"""
import logging
import random
import re
import threading
import time
from typing import List, Dict, Optional

from bs4 import BeautifulSoup

import settings
from content import net, posted_store

logger = logging.getLogger(__name__)

# style="...;background-image:url('https://cdn4.telesco.pe/file/....jpg')"
_BACKGROUND_URL_RE = re.compile(r"background-image\s*:\s*url\('([^']+)'\)")

# Обёртка фото и тег видео. Один селектор, а не два обхода: soupsieve отдаёт
# совпадения в порядке документа, поэтому смешанный альбом (фото + видео)
# сохраняет исходный порядок элементов.
_MEDIA_SELECTOR = "video[src], .tgme_widget_message_photo_wrap"

# Сколько страниц истории канала пролистываем за один обход, пока не наберём
# достаточно неопубликованных постов. Каждая страница — запрос к t.me примерно
# на 16-20 постов, поэтому предел нужен: у канала могут быть годы архива.
MAX_PAGES_PER_CHANNEL = 12

# Сколько новых постов на канал считаем достаточным, чтобы прекратить листать
WANTED_FRESH_PER_CHANNEL = 12


def extract_media(post) -> List[Dict[str, str]]:
    """Прямые ссылки на медиа поста: [{'url': ..., 'type': 'photo'|'video'}].

    Отдаём все найденные элементы, хотя публикуется из них ровно один
    (см. meme_scheduler.pick_candidates): остальные — резерв, если первый не
    скачался.

    Пустой список — в посте нечего скачивать (текст, стикер, файл-документ:
    у последних двух прямой ссылки на странице нет).
    """
    items: List[Dict[str, str]] = []
    seen = set()

    for tag in post.select(_MEDIA_SELECTOR):
        if tag.name == "video":
            url, media_type = tag.get("src"), "video"
        else:
            match = _BACKGROUND_URL_RE.search(tag.get("style") or "")
            url, media_type = (match.group(1) if match else None), "photo"

        # Дедуп по url: на каждое видео t.me печатает два <video> с одинаковым
        # src — размытую подложку и сам плеер. Без дедупа видео уехало бы дважды.
        if not url or not url.startswith("http") or url in seen:
            continue

        seen.add(url)
        items.append({"url": url, "type": media_type})

    return items


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
        self.posts_cache = []
        self.last_fetch_time = 0
        self.cache_ttl = 3600
        # Выбор поста идёт из рабочих потоков asyncio.to_thread, и планировщик с
        # /postnow могут попасть в него одновременно: без блокировки два вызова
        # выбрали бы один и тот же пост, а обновление кэша пошло бы дважды.
        self._lock = threading.Lock()

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
            # Получаем РЕАЛЬНЫЙ ID сообщения из data-post
            data_post = post.get('data-post')
            if not data_post:
                continue

            # data-post имеет формат: "channel_name/message_id"
            parts = data_post.split('/')
            if len(parts) != 2:
                continue

            real_message_id = parts[1]  # Это реальный ID для API

            # Ссылки достаём сразу: пост без скачиваемого медиа не должен попасть
            # в кандидаты и тратить попытку публикации. Раньше отбор шёл по
            # наличию обёртки *_photo_wrap / *_video_wrap / *_document_wrap, и
            # посты-документы проходили фильтр, хотя ссылки на файл в них нет.
            media = extract_media(post)
            if not media:
                continue

            result.append({
                'source_channel': source['chat_id'],
                'message_id': int(real_message_id),
                'source_name': source['name'],
                'media': media,
                'web_id': parts[0]  # Для информации
            })
            logger.debug(f"  Найден пост: data-post={data_post}, медиа: {len(media)}")

        if not result:
            # Посты есть, а медиа ни в одном не нашлось — это уже про вёрстку,
            # а не про «в канале только текст»
            net.log_layout_changed(
                f"мемы {source['name']}", source['url'],
                f"постов найдено {len(posts)}, но ни в одном нет "
                "<video src> или .tgme_widget_message_photo_wrap",
            )
            return []

        logger.info(f"✅ Найдено {len(result)} постов с медиа в {source['name']}")
        return result
    
    def collect_channel(self, source: Dict, limit: int = 100) -> List[Dict]:
        """Посты канала, начиная со свежих и глубже по архиву.

        Листаем, пока не наберём WANTED_FRESH_PER_CHANNEL ещё не опубликованных
        постов. На первой странице t.me показывает около 20 постов — за неделю
        работы бот их исчерпывает, и без долистывания публикации бы прекратились.
        """
        collected: List[Dict] = []
        fresh = 0
        before: Optional[int] = None

        for page in range(1, MAX_PAGES_PER_CHANNEL + 1):
            url = source['url'] if before is None else f"{source['url']}?before={before}"
            soup = self._fetch_page(url)
            if soup is None:
                break

            posts = self._extract_posts(soup, source, limit)
            if not posts:
                # Архив кончился либо страница не открылась — глубже смысла нет
                break

            collected.extend(posts)
            fresh += sum(
                1 for p in posts
                if not posted_store.is_post_posted(p['source_channel'], p['message_id'])
            )

            if fresh >= WANTED_FRESH_PER_CHANNEL:
                break

            # ?before=<самый старый id страницы> — так t.me отдаёт предыдущую
            next_before = min(p['message_id'] for p in posts)
            if before is not None and next_before >= before:
                # Страница не сдвинулась: дальше листать некуда
                break
            before = next_before

            logger.info(
                f"📖 {source['name']}: новых постов {fresh}, листаю историю "
                f"дальше (страница {page + 1}, до id {before})"
            )
            time.sleep(1)

        if collected:
            logger.info(
                f"✅ {source['name']}: собрано {len(collected)} постов с медиа, "
                f"из них ещё не публиковались {fresh}"
            )
        return collected

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
                posts = self.collect_channel(source, limit_per_channel)
                all_posts.extend(posts)
                time.sleep(1)
            except Exception as e:
                logger.error(f"❌ Ошибка парсинга {source['name']}: {e}")

        random.shuffle(all_posts)
        logger.info(f"📊 Всего собрано {len(all_posts)} постов с мемами")
        return all_posts

    def _fresh_posts(self) -> List[Dict]:
        """Посты из кэша, которых ещё не было в канале. Вызывать под self._lock."""
        return [
            p for p in self.posts_cache
            if not posted_store.is_post_posted(p['source_channel'], p['message_id'])
        ]

    def get_candidates(self, count: int = 1) -> List[Dict]:
        """До count разных неопубликованных постов, в случайном порядке.

        Отдаём сразу список, а не по одному посту на вызов: планировщик при
        осечке берёт следующего кандидата, и раньше он мог получить тот же пост
        снова — пост помечается опубликованным только после успешной отправки.
        """
        with self._lock:
            stale = time.time() - self.last_fetch_time > self.cache_ttl
            if stale or not self.posts_cache:
                logger.info("🔄 Обновление кэша постов с мемами...")
                self.posts_cache = self.get_all_posts(limit_per_channel=50)
                self.last_fetch_time = time.time()

            available = self._fresh_posts()

            if not available and not stale:
                # Кэш ещё свежий по времени, но в нём всё опубликовано: за час
                # канал мог пополниться, а история — долистаться глубже
                logger.info("🔄 В кэше не осталось новых постов, обновляю список...")
                self.posts_cache = self.get_all_posts(limit_per_channel=50)
                self.last_fetch_time = time.time()
                available = self._fresh_posts()

            if not available:
                # Историю не сбрасываем: «опубликовано один раз — больше не
                # берём» важнее того, чтобы в канале что-то появилось
                logger.warning(
                    "⚠️ Все посты из каналов-источников уже публиковались — "
                    "нужны новые каналы (/sources add) или /posted reset"
                )
                return []

            chosen = random.sample(available, min(count, len(available)))

        logger.info(
            f"🎯 Кандидаты ({len(chosen)} из {len(available)} неопубликованных): "
            + ", ".join(f"{p['source_name']}/{p['message_id']}" for p in chosen)
        )
        return chosen

    def get_random_meme_to_forward(self) -> Optional[Dict]:
        candidates = self.get_candidates(1)
        return candidates[0] if candidates else None


_meme_forwarder = None

def _get_forwarder() -> MemeForwarder:
    """Один экземпляр на процесс: в нём живут сессия и кэш постов."""
    global _meme_forwarder
    if _meme_forwarder is None:
        _meme_forwarder = MemeForwarder()
    return _meme_forwarder

def get_random_meme_to_forward() -> Optional[Dict]:
    return _get_forwarder().get_random_meme_to_forward()


def get_meme_candidates(count: int = 1) -> List[Dict]:
    """До count разных постов, которые ещё не публиковались. Пустой список — все были."""
    return _get_forwarder().get_candidates(count)


def fetch_post_media(source_channel: str, message_id: int) -> List[Dict[str, str]]:
    """Свежие ссылки на медиа конкретного поста. Пустой список — не получилось.

    Зачем заново, если ссылки уже есть в кэше: кэш живёт час (cache_ttl), а в
    url telesco.pe вшит token с меньшим сроком жизни, и скачивание по
    просроченной ссылке отвалится.

    Берём embed-версию страницы, а не t.me/<канал>/<id>: на обычной странице
    одиночного поста нет ни mp4, ни всех фото альбома — только og:image-превью
    первого кадра. Именно поэтому видео не публиковались.

    Сессия своя на вызов: функция зовётся из рабочих потоков, а requests.Session
    между потоками делить нельзя. Создание сессии дешёвое, cookies тут не нужны.
    """
    name = source_channel.lstrip('@')
    url = f"https://t.me/{name}/{message_id}?embed=1&mode=tme"

    response = net.get(
        url, session=net.new_session(), label=f"пост {name}/{message_id}",
    )
    if response is None:
        return []
    if response.status_code != 200:
        logger.warning(f"⚠️ {url}: HTTP {response.status_code}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    post = soup.select_one('.tgme_widget_message')
    if post is None:
        net.log_layout_changed(
            f"пост {name}/{message_id}", url, "нет .tgme_widget_message",
        )
        return []

    return extract_media(post)

def invalidate_cache() -> None:
    """Сбрасывает кэш постов, чтобы правки /sources подействовали сразу.

    История публикаций (posted_store) при этом не трогается: иначе после каждой
    правки списка каналов в канал поехали бы уже отправленные мемы.
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
