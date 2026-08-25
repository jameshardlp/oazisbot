"""Проверка свежести контента по тексту и URL.

Работает только со строкой, саму картинку не смотрит — это делает
content.vision.verify_photo_with_deepseek.
"""
import re
from datetime import datetime
from typing import Optional


def min_date() -> datetime:
    """1 января текущего года.

    Считается на каждый вызов, а не один раз при импорте: процесс живёт месяцами
    и, пережив Новый год, иначе навсегда остался бы в году своего запуска.
    """
    return datetime(datetime.now().year, 1, 1)

def _words_in(text: str) -> set:
    """Разбивает URL на слова, чтобы искать совпадения по слову, а не по подстроке.

    Без этого 'man' находился внутри 'woman', 'male' внутри 'female',
    а 'old' внутри 'golden' — и валидные фото отбраковывались.
    """
    return set(re.split(r'[^a-zа-я0-9]+', text.lower()))

def _has_phrase(text: str, phrases) -> bool:
    """Совпадение по границам слов: работает и для фраз из нескольких слов."""
    words = _words_in(text)
    for phrase in phrases:
        parts = [p for p in re.split(r'[^a-zа-я0-9]+', phrase.lower()) if p]
        if not parts:
            continue
        if len(parts) == 1:
            if parts[0] in words:
                return True
        elif re.search(r'\b' + r'[^a-zа-я0-9]+'.join(map(re.escape, parts)) + r'\b', text.lower()):
            return True
    return False

def parse_date_from_text(text: str) -> Optional[datetime]:
    if not text:
        return None

    date_patterns = [
        r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})',
        r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})',
        r'(\d{1,2})\s+(янв|фев|мар|апр|май|июн|июл|авг|сен|окт|ноя|дек)\s+(\d{4})',
        r'(\d{4})\s+год',
        r'(\d{2})\.(\d{2})\.(\d{4})',
    ]

    months_map = {
        'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4, 'май': 5, 'июн': 6,
        'июл': 7, 'авг': 8, 'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12
    }

    for pattern in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            groups = match.groups()
            try:
                if len(groups) == 3:
                    if groups[0].isdigit() and len(groups[0]) == 4:
                        year = int(groups[0])
                        month = int(groups[1])
                        day = int(groups[2])
                    elif groups[2].isdigit() and len(groups[2]) == 4:
                        day = int(groups[0])
                        month = int(groups[1])
                        year = int(groups[2])
                    elif groups[1].lower() in months_map:
                        day = int(groups[0])
                        month = months_map[groups[1].lower()]
                        year = int(groups[2])
                    else:
                        continue

                    # Верхняя граница — от текущего года, а не константа:
                    # захардкоженный потолок протух бы так же, как MIN_DATE
                    if 2000 <= year <= datetime.now().year + 1 and 1 <= month <= 12 and 1 <= day <= 31:
                        return datetime(year, month, day)
            except (ValueError, IndexError):
                continue

    return None

def check_date_in_content(content: str, url: str = "") -> bool:
    text_to_check = content
    if url:
        text_to_check = f"{text_to_check} {url}"

    threshold = min_date()

    date = parse_date_from_text(text_to_check)
    if date:
        return date >= threshold

    # По границам слов: подстрочный поиск отбраковывал 'img_20250.jpg' по '2025'
    # и 'golden' по 'old'.
    year_match = re.search(r'\b(19\d{2}|20[0-3]\d)\b', text_to_check)
    if year_match:
        year = int(year_match.group(1))
        if year < threshold.year:
            return False

    if _has_phrase(text_to_check, ['ретро', 'старый', 'архив', 'давно', 'retro', 'vintage', 'archive']):
        return False

    return True
