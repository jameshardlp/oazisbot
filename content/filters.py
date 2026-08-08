"""Эвристики по URL и тексту: этничность, возраст, свежесть контента.

Работают только со строкой URL, саму картинку не смотрят — это делает
bot.content.vision.verify_*.
"""
import re
from datetime import datetime
from typing import Optional

MIN_DATE = datetime(2026, 1, 1)

ASIAN_KEYWORDS = [
    'asian', 'japanese', 'korean', 'chinese', 'thai', 'vietnamese',
    'filipino', 'indonesian', 'malaysian', 'singaporean', 'taiwanese',
    'mongolian', 'burmese', 'cambodian', 'laotian', 'east asian',
    'south east asian', 'oriental', 'asia girl', 'asia woman',
    'japan', 'korea', 'china', 'thailand', 'vietnam', 'philippines',
]

NON_ASIAN_KEYWORDS = [
    'african', 'black', 'white', 'caucasian', 'european', 'american',
    'latina', 'mexican', 'brazilian', 'indian', 'middle eastern',
    'arab', 'persian', 'turkish', 'russian', 'ukrainian', 'polish',
]

ASIAN_NAMES = [
    'yuki', 'haruka', 'sakura', 'ai', 'miyu', 'rina', 'mika', 'kaori',
    'hana', 'momoko', 'chihiro', 'nanami', 'hinata', 'yui', 'mizuki',
    'yeon', 'jiwoo', 'eunji', 'yuna', 'hyejin', 'sooyoung', 'jisoo',
]

AGE_POSITIVE_KEYWORDS = [
    '18', '19', '20', '21', '22', '23', '24', '25',
    '26', '27', '28', '29', '30',
    '18year', '19year', '20year', '21year', '22year',
    '18yo', '19yo', '20yo', '21yo', '22yo', '23yo',
    '20s', 'twenties', 'college', 'university',
    'student', 'freshman', 'sophomore',
]

CHILD_EXCLUDE_WORDS = [
    'child', 'children', 'kid', 'kids', 'baby', 'babies', 'toddler',
    'infant', 'preschool', 'kindergarten', 'schoolgirl', 'schoolboy',
    'girl scout', 'boy scout', 'cub scout', 'teen', 'teenager',
    'minor', 'underage', 'little girl', 'little boy', 'young girl',
    'young boy', 'daughter', 'son', 'family', 'family photo',
    'childhood', 'baby girl', 'baby boy', 'newborn', 'cute baby',
    'child model', 'kid model', 'baby model', 'toddler girl', 'toddler boy',
]

MEN_EXCLUDE_WORDS = [
    'man', 'men', 'boy', 'male', 'guy', 'dude', 'brother',
    'father', 'husband', 'boyfriend', 'gentleman', 'sir',
    'bloke', 'chap', 'fellow', 'lad', 'young man',
]

TRADITIONAL_EXCLUDE = [
    'kimono', 'hanbok', 'cheongsam', 'qi pao', 'sari', 'ao dai',
    'traditional', 'folk costume', 'national dress', 'hanfu',
]

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
                    
                    if 2000 <= year <= 2030 and 1 <= month <= 12 and 1 <= day <= 31:
                        return datetime(year, month, day)
            except (ValueError, IndexError):
                continue
    
    return None

def check_date_in_content(content: str, url: str = "") -> bool:
    text_to_check = content
    if url:
        text_to_check = f"{text_to_check} {url}"
    
    date = parse_date_from_text(text_to_check)
    if date:
        return date >= MIN_DATE
    
    # По границам слов: подстрочный поиск отбраковывал 'img_20250.jpg' по '2025'
    # и 'golden' по 'old'.
    year_match = re.search(r'\b(19\d{2}|20[0-2]\d)\b', text_to_check)
    if year_match:
        year = int(year_match.group(1))
        if year < MIN_DATE.year:
            return False

    if _has_phrase(text_to_check, ['ретро', 'старый', 'архив', 'давно', 'retro', 'vintage', 'archive']):
        return False

    return True

def is_photo_valid(url: str) -> bool:
    if not url:
        return False
    if is_child_photo(url):
        return False
    if has_man_in_photo(url):
        return False
    # is_asian_photo здесь намеренно не вызывается: URL с CDN
    # (pexels.com/photos/123456.jpeg) не содержит признаков этничности,
    # поэтому проверка отбраковывала все валидные результаты.
    # Этничность проверяет verify_asia_photo_with_deepseek по самой картинке.
    if not is_age_appropriate(url):
        return False
    if is_traditional_clothing(url):
        return False
    unwanted = ['naked', 'nude', 'porn', 'xxx', 'sex', 'erotic', 'bikini']
    if _has_phrase(url, unwanted):
        return False
    return True

def is_child_photo(url: str) -> bool:
    if not url:
        return False
    if _has_phrase(url, CHILD_EXCLUDE_WORDS):
        return True
    # Только явное указание возраста ("18yo", "age 16"), а не любое число в URL:
    # прежний \b(0|1|...|17)\b ловил размеры, id и даты в пути.
    if re.search(r'\b(?:age[_\-\s]*)?(?:[0-9]|1[0-7])\s*(?:yo|y/o|years?)\b', url.lower()):
        return True
    if re.search(r'\b(?:grade|class|school)[_\-\s]*[1-9]\b', url.lower()):
        return True
    return False

def has_man_in_photo(url: str) -> bool:
    if not url:
        return False
    return _has_phrase(url, MEN_EXCLUDE_WORDS)

def is_asian_photo(url: str, additional_context: str = "") -> bool:
    if not url:
        return False
    text_to_check = url.lower()
    if additional_context:
        text_to_check += " " + additional_context.lower()
    if _has_phrase(text_to_check, ASIAN_KEYWORDS):
        return True
    if _has_phrase(text_to_check, NON_ASIAN_KEYWORDS):
        return False
    if _has_phrase(text_to_check, ASIAN_NAMES):
        return True
    if _has_phrase(text_to_check, AGE_POSITIVE_KEYWORDS):
        if _has_phrase(text_to_check, ['blonde', 'blue eyes', 'green eyes', 'redhead', 'ginger']):
            return False
        return True
    asian_features = [
        'slender', 'petite', 'olive skin', 'dark hair', 'black hair',
        'straight hair', 'bangs', 'double eyelid', 'monolid',
        'kawaii', 'cute', 'innocent', 'pure', 'delicate',
        'small face', 'fair skin',
    ]
    if _has_phrase(text_to_check, asian_features):
        return True
    asian_domains = ['.jp', '.kr', '.cn', '.tw', '.hk', '.mo', '.sg', '.th', '.vn', '.ph', '.my', '.id']
    host = url.lower().split('/')[2] if '://' in url else url.lower().split('/')[0]
    for domain in asian_domains:
        if host.endswith(domain):
            return True
    return False

def is_age_appropriate(url: str) -> bool:
    if not url:
        return False
    if is_child_photo(url):
        return False
    if _has_phrase(url, AGE_POSITIVE_KEYWORDS):
        return True
    if _has_phrase(url, ['mature', 'old', 'senior', 'elderly']):
        return False
    return True

def is_traditional_clothing(url: str) -> bool:
    if not url:
        return False
    return _has_phrase(url, TRADITIONAL_EXCLUDE)
