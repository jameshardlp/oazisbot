"""Память о том, что уже уходило в канал: один мем публикуется ровно один раз.

Раньше эту роль играло множество sent_cache внутри MemeForwarder, и оно не
работало по трём причинам: жило только в памяти (перезапуск — и весь канал
можно постить заново), сбрасывалось само, как только все посты помечены
отправленными, и ключевалось одним message_id без имени канала, так что пост
№1000 из одного канала прятал пост №1000 из другого.

Ключей на каждое медиа три, от дешёвого к надёжному:

* post — "канал/id" сообщения. Стабилен всегда, известен до всякой сети, но
  ловит только повтор ровно того же поста.
* file — хэш пути в url телеско.pe. Для видео путь (d0e852e6b9.mp4) — это
  сам файл, поэтому один и тот же клип узнаётся в разных постах и каналах ещё
  до скачивания. Для фото путь — подписанная ссылка, живёт недолго, так что
  ключ полезен лишь как быстрая подсказка.
* sha — sha256 самих байтов. Единственный надёжный признак: узнаёт тот же
  файл, даже если он перезалит в другой канал под новой ссылкой. Требует
  скачивания, поэтому проверяется последним.

Записи не вытесняются, пока их меньше MAX_RECORDS: «опубликовано — больше не
берём» ценнее экономии на файле в пару мегабайт.
"""
import hashlib
import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

from config import POSTED_FILE

logger = logging.getLogger(__name__)

# При 10-20 постах в сутки это годы истории. Дальше вытесняем самые старые:
# файл не должен расти без границы, а мем годичной давности повторить не жалко.
MAX_RECORDS = 20000

# Хватает, чтобы случайных совпадений не было, и вдвое короче полного sha256
_KEY_LEN = 16

_lock = threading.RLock()
_records: Optional[List[Dict[str, Any]]] = None
_posts: set = set()
_files: set = set()
_shas: set = set()
_loaded_from_file = False


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()[:_KEY_LEN]


def post_key(source_channel: str, message_id: Any) -> str:
    """'@noviop', 17188 → 'noviop/17188'. Регистр имени канала t.me не различает."""
    name = str(source_channel or "").strip().lstrip("@").lower()
    return f"{name}/{message_id}"


def file_key(url: str) -> str:
    """Ключ по пути в url, без query: token в нём меняется каждую выдачу."""
    if not url:
        return ""
    return _digest(urlsplit(url).path)


def content_key(data: bytes) -> str:
    """Ключ по самим байтам файла."""
    return hashlib.sha256(data).hexdigest()[:_KEY_LEN]


def _index(records: List[Dict[str, Any]]) -> None:
    """Перестраивает множества для проверок. Вызывать под _lock."""
    global _posts, _files, _shas
    _posts = {r["post"] for r in records if r.get("post")}
    _files = {r["file"] for r in records if r.get("file")}
    _shas = {r["sha"] for r in records if r.get("sha")}


def _load() -> List[Dict[str, Any]]:
    """Читает файл один раз за процесс. Вызывать под _lock."""
    global _records, _loaded_from_file
    if _records is not None:
        return _records

    try:
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError:
        # Первый запуск — обычное дело
        _records = []
        _loaded_from_file = False
        _index(_records)
        return _records
    except (OSError, ValueError) as e:
        # Битый файл не должен ронять публикацию: хуже повтора мема ничего не
        # случится, а молча потерять всю историю нельзя — пишем в лог громко
        logger.error(f"❌ Не удалось прочитать {POSTED_FILE}: {e}. История публикаций пуста")
        _records = []
        _loaded_from_file = False
        _index(_records)
        return _records

    records = []
    if isinstance(raw, dict):
        items = raw.get("items")
    else:
        # Совместимость: если файл когда-то был просто списком
        items = raw

    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            record = {
                "post": str(item.get("post") or ""),
                "file": str(item.get("file") or ""),
                "sha": str(item.get("sha") or ""),
                "ts": int(item.get("ts") or 0) if str(item.get("ts") or 0).isdigit() else 0,
            }
            if record["post"] or record["file"] or record["sha"]:
                records.append(record)
    else:
        logger.warning(f"⚠️ {POSTED_FILE}: не найден список items, история публикаций пуста")

    _records = records
    _loaded_from_file = True
    _index(_records)
    logger.info(f"🧠 История публикаций: {len(_records)} медиа из {store_path()}")
    return _records


def _save() -> bool:
    """Пишет файл через временный + os.replace. Вызывать под _lock.

    Без replace обрыв процесса во время записи оставил бы обрезанный JSON —
    и вся история публикаций пропала бы, то есть канал поехал бы по второму разу.
    """
    tmp = f"{POSTED_FILE}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"items": _records}, f, ensure_ascii=False)
        os.replace(tmp, POSTED_FILE)
        return True
    except OSError as e:
        logger.error(f"❌ Не удалось сохранить {POSTED_FILE}: {e}")
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return False


def store_path() -> str:
    return os.path.abspath(POSTED_FILE)


def loaded_from_file() -> bool:
    """False — файла не было, история пуста и все мемы считаются новыми."""
    with _lock:
        _load()
        return _loaded_from_file


def count() -> int:
    with _lock:
        return len(_load())


def is_post_posted(source_channel: str, message_id: Any) -> bool:
    with _lock:
        _load()
        return post_key(source_channel, message_id) in _posts


def is_file_posted(url: str) -> bool:
    key = file_key(url)
    if not key:
        return False
    with _lock:
        _load()
        return key in _files


def is_content_posted(data: bytes) -> bool:
    with _lock:
        _load()
        return content_key(data) in _shas


def remember(
    source_channel: str, message_id: Any, url: str, data: Optional[bytes] = None
) -> bool:
    """Запоминает опубликованное медиа. Зовётся только после успешной отправки.

    Помечать при выборе поста нельзя: неудачная попытка (t.me не отдал файл,
    Telegram отклонил видео) выбросила бы мем навсегда, ни разу не показав его.
    """
    record = {
        "post": post_key(source_channel, message_id),
        "file": file_key(url),
        "sha": content_key(data) if data else "",
        "ts": int(time.time()),
    }

    with _lock:
        records = _load()
        records.append(record)

        if len(records) > MAX_RECORDS:
            # Срезаем самые старые записи одним куском, а не по одной
            del records[: len(records) - MAX_RECORDS]
            _index(records)
            logger.info(f"🧠 История публикаций подрезана до {MAX_RECORDS} записей")
        else:
            if record["post"]:
                _posts.add(record["post"])
            if record["file"]:
                _files.add(record["file"])
            if record["sha"]:
                _shas.add(record["sha"])

        return _save()


def forget_all() -> int:
    """Забывает всё: после этого канал можно постить с начала. Возвращает, сколько забыто."""
    global _records
    with _lock:
        was = len(_load())
        _records = []
        _index(_records)
        _save()
    logger.warning(f"🧠 История публикаций очищена ({was} медиа) — мемы могут пойти по второму разу")
    return was


def describe() -> str:
    """Строка для /posted и логов старта."""
    with _lock:
        _load()
        total = len(_records or [])
        from_file = _loaded_from_file

    if not total:
        if from_file:
            return f"история публикаций пуста ({store_path()})"
        return f"файла {store_path()} нет — все мемы считаются новыми"

    return f"{total} медиа запомнено, файл {store_path()}"
