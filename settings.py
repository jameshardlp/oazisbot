"""Настройки, которые владелец меняет командами на ходу.

Отличие от config.py: там переменные окружения, читаются один раз при старте и
меняются только перезапуском. Здесь — интервал постинга, режим контента и
список каналов с мемами: их правят командами /interval, /mode и /sources, и они
переживают перезапуск через JSON-файл.

Модуль лежит в корне, а не в bot_modules/: его импортирует content/meme_forwarder,
а зависимость content → bot_modules перевернула бы слои.
"""
import asyncio
import json
import logging
import random
import re
from typing import Any, Dict, List, Optional, Tuple

from config import CONTENT_MODE, CONTENT_MODES, SETTINGS_FILE

logger = logging.getLogger(__name__)

# Значения по умолчанию — то, что раньше было захардкожено в планировщиках
# (MIN_INTERVAL/MAX_INTERVAL) и в content/meme_forwarder.MEME_SOURCES
DEFAULT_MIN_MINUTES = 60
DEFAULT_MAX_MINUTES = 180
DEFAULT_MEME_CHANNELS = [
    "videos_dolboyoba",
    "shitcollection",
    "postleftism",
    "noviop",
]

# CONTENT_MODE из окружения — только начальное значение: как только режим сменили
# командой /mode, решает файл настроек, иначе команда сбрасывалась бы перезапуском
DEFAULT_CONTENT_MODE = CONTENT_MODE

CONTENT_MODE_LABELS = {
    "streamers": "посты про стримеров (текст + ссылка на клип)",
    "memes": "мемы из каналов-источников",
}

# Границы, в которых принимаем интервал от админа
MIN_ALLOWED_MINUTES = 1
MAX_ALLOWED_MINUTES = 7 * 24 * 60  # неделя

# Telegram режет частый постинг в канал; ниже этого порога предупреждаем
FLOOD_WARNING_MINUTES = 5

# Имя канала в Telegram: латиница, цифры, подчёркивание, 4-32 символа
_CHANNEL_RE = re.compile(r'^[A-Za-z0-9_]{4,32}$')

# Планировщик спит в wait_for_next_post(); событие будит его, когда админ
# сменил интервал, — иначе новое значение подействовало бы только через часы
changed = asyncio.Event()

# Смена режима будит надзорную задачу в bot.py: она гасит текущий планировщик и
# поднимает тот, что соответствует новому режиму
mode_changed = asyncio.Event()

_settings: Optional[Dict[str, Any]] = None


def _defaults() -> Dict[str, Any]:
    return {
        "content_mode": DEFAULT_CONTENT_MODE,
        "interval_min_minutes": DEFAULT_MIN_MINUTES,
        "interval_max_minutes": DEFAULT_MAX_MINUTES,
        "meme_channels": list(DEFAULT_MEME_CHANNELS),
    }


def _sanitize(raw: Any) -> Dict[str, Any]:
    """Приводит прочитанное к валидному виду, подставляя дефолты вместо мусора.

    Файл правят руками, и одно кривое значение не должно ронять планировщик:
    любая непонятная часть заменяется значением по умолчанию с предупреждением.
    """
    result = _defaults()
    if not isinstance(raw, dict):
        logger.warning(f"⚠️ {SETTINGS_FILE}: ожидался объект, взяты значения по умолчанию")
        return result

    mode = raw.get("content_mode")
    if isinstance(mode, str) and mode.strip().lower() in CONTENT_MODES:
        result["content_mode"] = mode.strip().lower()
    elif mode is not None:
        logger.warning(
            f"⚠️ {SETTINGS_FILE}: неизвестный режим {mode!r}, "
            f"использую {DEFAULT_CONTENT_MODE}"
        )

    lo = raw.get("interval_min_minutes")
    hi = raw.get("interval_max_minutes")
    # bool — подкласс int, но интервал в True минут смысла не имеет
    if (isinstance(lo, int) and not isinstance(lo, bool)
            and isinstance(hi, int) and not isinstance(hi, bool)
            and MIN_ALLOWED_MINUTES <= lo <= hi <= MAX_ALLOWED_MINUTES):
        result["interval_min_minutes"] = lo
        result["interval_max_minutes"] = hi
    elif lo is not None or hi is not None:
        logger.warning(
            f"⚠️ {SETTINGS_FILE}: некорректный интервал ({lo!r}, {hi!r}), "
            f"использую {DEFAULT_MIN_MINUTES}-{DEFAULT_MAX_MINUTES} мин"
        )

    channels = raw.get("meme_channels")
    if isinstance(channels, list):
        clean = []
        for item in channels:
            name = normalize_channel(item) if isinstance(item, str) else None
            if name and name not in clean:
                clean.append(name)
        # Пустой список — это осознанный выбор админа (/sources del всех),
        # а не повод молча вернуть дефолты
        result["meme_channels"] = clean
        if len(clean) != len(channels):
            logger.warning(
                f"⚠️ {SETTINGS_FILE}: часть имён каналов отброшена "
                f"(было {len(channels)}, осталось {len(clean)})"
            )
    elif channels is not None:
        logger.warning(
            f"⚠️ {SETTINGS_FILE}: meme_channels не список ({type(channels).__name__}), "
            "использую список по умолчанию"
        )

    return result


def load(force: bool = False) -> Dict[str, Any]:
    """Читает настройки из файла (с кэшем). При любой ошибке — значения по умолчанию."""
    global _settings
    if _settings is not None and not force:
        return _settings

    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError:
        # Обычная ситуация при первом запуске — не шумим
        _settings = _defaults()
        return _settings
    except (OSError, ValueError) as e:
        logger.warning(f"⚠️ Не удалось прочитать {SETTINGS_FILE}: {e}")
        _settings = _defaults()
        return _settings

    _settings = _sanitize(raw)
    return _settings


def save() -> bool:
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(load(), f, ensure_ascii=False, indent=2)
        return True
    except OSError as e:
        logger.error(f"❌ Не удалось сохранить {SETTINGS_FILE}: {e}")
        return False


# ===== РЕЖИМ КОНТЕНТА =====

def get_content_mode() -> str:
    return load()["content_mode"]


def set_content_mode(mode: str) -> bool:
    """Сохраняет режим и будит надзорную задачу, чтобы та сменила планировщик."""
    data = load()
    data["content_mode"] = mode
    ok = save()
    mode_changed.set()
    logger.info(f"⚙️ Режим контента изменён: {mode}")
    return ok


def describe_content_mode() -> str:
    """'memes — мемы из каналов-источников'."""
    mode = get_content_mode()
    return f"{mode} — {CONTENT_MODE_LABELS.get(mode, 'неизвестный режим')}"


# ===== ИНТЕРВАЛ =====

def get_interval_minutes() -> Tuple[int, int]:
    data = load()
    return data["interval_min_minutes"], data["interval_max_minutes"]


def set_interval_minutes(lo: int, hi: int) -> bool:
    """Сохраняет новый диапазон и будит спящий планировщик."""
    data = load()
    data["interval_min_minutes"] = lo
    data["interval_max_minutes"] = hi
    ok = save()
    changed.set()
    logger.info(f"⚙️ Интервал постинга изменён: {lo}-{hi} мин")
    return ok


def next_interval_seconds() -> int:
    lo, hi = get_interval_minutes()
    return random.randint(lo * 60, hi * 60)


def format_interval(seconds: int) -> str:
    """'1ч 30м' / '45м' — для логов и ответов бота."""
    minutes = max(1, seconds // 60)
    hours, minutes = divmod(minutes, 60)
    if hours and minutes:
        return f"{hours}ч {minutes}м"
    if hours:
        return f"{hours}ч"
    return f"{minutes}м"


def describe_interval() -> str:
    """'60-180 мин' или '45 мин', если границы совпали."""
    lo, hi = get_interval_minutes()
    return f"{lo} мин" if lo == hi else f"{lo}-{hi} мин"


async def wait_for_next_post(seconds: int) -> bool:
    """Спит до следующего поста. True — если разбудила смена интервала.

    Без этого события новый интервал подействовал бы только через несколько
    часов: планировщик в этот момент сидит в ожидании по старому значению.
    """
    changed.clear()
    try:
        await asyncio.wait_for(changed.wait(), timeout=seconds)
        return True
    except asyncio.TimeoutError:
        return False


# ===== КАНАЛЫ-ИСТОЧНИКИ =====

def normalize_channel(raw: str) -> Optional[str]:
    """'@name', 'https://t.me/s/name', 't.me/name' → 'name'. None, если не имя канала."""
    if not isinstance(raw, str):
        return None

    name = raw.strip()
    name = re.sub(r'^https?://', '', name, flags=re.IGNORECASE)
    name = re.sub(r'^(www\.)?t(elegram)?\.me/', '', name, flags=re.IGNORECASE)
    name = re.sub(r'^s/', '', name, flags=re.IGNORECASE)  # t.me/s/name — веб-превью
    name = name.split('/')[0].split('?')[0].lstrip('@').strip()

    return name if _CHANNEL_RE.match(name) else None


def get_meme_channels() -> List[str]:
    return list(load()["meme_channels"])


def add_meme_channel(name: str) -> bool:
    """True — добавлен, False — уже был в списке."""
    data = load()
    if name in data["meme_channels"]:
        return False
    data["meme_channels"].append(name)
    save()
    logger.info(f"⚙️ Канал-источник добавлен: {name}")
    return True


def remove_meme_channel(name: str) -> bool:
    """True — удалён, False — такого не было."""
    data = load()
    if name not in data["meme_channels"]:
        return False
    data["meme_channels"].remove(name)
    save()
    logger.info(f"⚙️ Канал-источник удалён: {name}")
    return True


def reset_meme_channels() -> List[str]:
    data = load()
    data["meme_channels"] = list(DEFAULT_MEME_CHANNELS)
    save()
    logger.info("⚙️ Список каналов-источников сброшен к значениям по умолчанию")
    return list(data["meme_channels"])
