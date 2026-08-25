"""Единый HTTP-клиент: общая сессия, таймауты, ретраи.

Раньше USER_AGENT / REQUEST_TIMEOUT / MAX_RETRIES / RETRY_DELAY дублировались
в search.py, image_search.py и channel_parser.py, причём ретраи были только
в двух из трёх, а в meme_scheduler.py их не было вовсе.

request() возвращает Optional[Response]: None означает «ответа получить не удалось»,
а не «сервер ответил ошибкой». Разбор кодов остаётся на вызывающем — deepseek.py,
например, сам различает 400 и 200, поэтому 4xx (кроме 429) отдаётся как есть,
без повторов.
"""
import logging
import random
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
REQUEST_TIMEOUT = 15
MAX_RETRIES = 3
RETRY_DELAY = 2
MAX_RETRY_DELAY = 30

# Коды, при которых имеет смысл повторить запрос. Остальные 4xx — это ответ
# сервера по существу, повторять его бессмысленно.
RETRY_STATUS = {429, 500, 502, 503, 504}

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def new_session() -> requests.Session:
    """Отдельная сессия с общими заголовками — для парсеров со своими cookies."""
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    return session


_session = new_session()


def _retry_delay(response: Optional[requests.Response], attempt: int) -> float:
    """Пауза перед повтором: уважает Retry-After, иначе экспонента с джиттером."""
    if response is not None:
        header = response.headers.get("Retry-After")
        if header:
            try:
                return min(float(header), MAX_RETRY_DELAY)
            except ValueError:
                pass
    return min(RETRY_DELAY * (2 ** attempt) + random.uniform(0, 1), MAX_RETRY_DELAY)


def request(
    method: str,
    url: str,
    *,
    timeout: float = REQUEST_TIMEOUT,
    retries: int = MAX_RETRIES,
    label: str = "",
    session: Optional[requests.Session] = None,
    **kwargs,
) -> Optional[requests.Response]:
    """Запрос с таймаутом и ретраями.

    Args:
        label: как называть источник в логах (например, "Bing Картинки").
        session: своя сессия, если нужны отдельные cookies.

    Returns:
        Response — включая 4xx и последний неудачный 5xx, чтобы вызывающий сам
        разобрал код. None — за все попытки ответа не получили.
    """
    what = label or url
    http = session or _session

    for attempt in range(retries):
        last_attempt = attempt == retries - 1
        response: Optional[requests.Response] = None
        reason = ""

        try:
            response = http.request(method, url, timeout=timeout, **kwargs)
        except requests.exceptions.Timeout:
            reason = f"таймаут {timeout}с"
        except requests.exceptions.ConnectionError:
            reason = "нет соединения"
        except requests.exceptions.RequestException as e:
            logger.warning(f"⚠️ {what}: запрос не выполнен — {e}")
            return None

        if response is not None:
            if response.status_code not in RETRY_STATUS:
                return response
            reason = f"HTTP {response.status_code}"

        if last_attempt:
            logger.warning(f"⚠️ {what}: {reason} — попытки исчерпаны ({retries})")
            return response

        delay = _retry_delay(response, attempt)
        logger.warning(
            f"⚠️ {what}: {reason}, повтор через {delay:.1f}с (попытка {attempt + 1}/{retries})"
        )
        time.sleep(delay)

    return None


def get(url: str, **kwargs) -> Optional[requests.Response]:
    return request("GET", url, **kwargs)


def post(url: str, **kwargs) -> Optional[requests.Response]:
    return request("POST", url, **kwargs)


def log_layout_changed(source: str, url: str = "", detail: str = "") -> None:
    """Страница загрузилась, но распарсить нечего.

    Отдельный уровень логирования от «ничего не нашлось»: пустой результат при
    успешном HTTP 200 почти всегда означает, что у источника поменялась вёрстка
    и регулярка/селектор больше не совпадает.
    """
    parts = [f"⚠️ {source}: страница загрузилась, но данные не найдены"]
    if detail:
        parts.append(f"({detail})")
    parts.append("— вероятно изменилась вёрстка источника")
    if url:
        parts.append(f"| {url}")
    logger.warning(" ".join(parts))
