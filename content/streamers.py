"""Справочник стримеров: склонения, поисковые запросы, стилевые промпты."""
import random
from typing import Tuple

STREAMER_INFO = {
    'voodoosh': {
        'name': 'Вудуш', 'gender': 'male', 'nominative': 'Вудуш',
        'genitive': 'Вудуша', 'dative': 'Вудушу', 'accusative': 'Вудуша',
        'instrumental': 'Вудушем', 'prepositional': 'Вудуше',
        'pronoun': 'он', 'possessive': 'его',
        'verb_past_male': 'сделал', 'verb_past_female': 'сделала',
        'verb_present': 'делает', 'verb_future': 'сделает',
        'display_name': 'Вудуш'
    },
    'praden': {
        'name': 'Праден', 'gender': 'male', 'nominative': 'Праден',
        'genitive': 'Прадена', 'dative': 'Прадену', 'accusative': 'Прадена',
        'instrumental': 'Праденом', 'prepositional': 'Прадене',
        'pronoun': 'он', 'possessive': 'его',
        'verb_past_male': 'сделал', 'verb_past_female': 'сделала',
        'verb_present': 'делает', 'verb_future': 'сделает',
        'display_name': 'Праден'
    },
    'bratishkinoff': {
        'name': 'Братишкин', 'gender': 'male', 'nominative': 'Братишкин',
        'genitive': 'Братишкина', 'dative': 'Братишкину', 'accusative': 'Братишкина',
        'instrumental': 'Братишкиным', 'prepositional': 'Братишкине',
        'pronoun': 'он', 'possessive': 'его',
        'verb_past_male': 'сделал', 'verb_past_female': 'сделала',
        'verb_present': 'делает', 'verb_future': 'сделает',
        'display_name': 'Братишкин'
    },
    'sasavot': {
        'name': 'Сасавот', 'gender': 'male', 'nominative': 'Сасавот',
        'genitive': 'Сасавота', 'dative': 'Сасавоту', 'accusative': 'Сасавота',
        'instrumental': 'Сасавотом', 'prepositional': 'Сасавоте',
        'pronoun': 'он', 'possessive': 'его',
        'verb_past_male': 'сделал', 'verb_past_female': 'сделала',
        'verb_present': 'делает', 'verb_future': 'сделает',
        'display_name': 'Сасавот'
    },
    'alina_rin': {
        'name': 'Алина Рин', 'gender': 'female', 'nominative': 'Алина Рин',
        'genitive': 'Алины Рин', 'dative': 'Алине Рин', 'accusative': 'Алину Рин',
        'instrumental': 'Алиной Рин', 'prepositional': 'Алине Рин',
        'pronoun': 'она', 'possessive': 'её',
        'verb_past_male': 'сделал', 'verb_past_female': 'сделала',
        'verb_present': 'делает', 'verb_future': 'сделает',
        'display_name': 'Алина Рин'
    },
    'lasqa': {
        'name': 'Ласка', 'gender': 'male', 'nominative': 'Ласка',
        'genitive': 'Ласки', 'dative': 'Ласке', 'accusative': 'Ласку',
        'instrumental': 'Лаской', 'prepositional': 'Ласке',
        'pronoun': 'он', 'possessive': 'его',
        'verb_past_male': 'сделал', 'verb_past_female': 'сделала',
        'verb_present': 'делает', 'verb_future': 'сделает',
        'display_name': 'Ласка'
    },
    'arrowwoods': {
        'name': 'Аравудус', 'gender': 'male', 'nominative': 'Аравудус',
        'genitive': 'Аравудуса', 'dative': 'Аравудусу', 'accusative': 'Аравудуса',
        'instrumental': 'Аравудусом', 'prepositional': 'Аравудусе',
        'pronoun': 'он', 'possessive': 'его',
        'verb_past_male': 'сделал', 'verb_past_female': 'сделала',
        'verb_present': 'делает', 'verb_future': 'сделает',
        'display_name': 'Аравудус'
    },
    'evelone': {
        'name': 'Эвелон', 'gender': 'male', 'nominative': 'Эвелон',
        'genitive': 'Эвелона', 'dative': 'Эвелону', 'accusative': 'Эвелона',
        'instrumental': 'Эвелоном', 'prepositional': 'Эвелоне',
        'pronoun': 'он', 'possessive': 'его',
        'verb_past_male': 'сделал', 'verb_past_female': 'сделала',
        'verb_present': 'делает', 'verb_future': 'сделает',
        'display_name': 'Эвелон'
    },
    'buster': {
        'name': 'Бустер', 'gender': 'male', 'nominative': 'Бустер',
        'genitive': 'Бустера', 'dative': 'Бустеру', 'accusative': 'Бустера',
        'instrumental': 'Бустером', 'prepositional': 'Бустере',
        'pronoun': 'он', 'possessive': 'его',
        'verb_past_male': 'сделал', 'verb_past_female': 'сделала',
        'verb_present': 'делает', 'verb_future': 'сделает',
        'display_name': 'Бустер'
    },
    # ===== НОВЫЙ СТРИМЕР: НЕНОРМОВА =====
    'nenormova': {
        'name': 'Ненормова', 'gender': 'female', 'nominative': 'Ненормова',
        'genitive': 'Ненормовой', 'dative': 'Ненормовой', 'accusative': 'Ненормову',
        'instrumental': 'Ненормовой', 'prepositional': 'Ненормовой',
        'pronoun': 'она', 'possessive': 'её',
        'verb_past_male': 'сделала', 'verb_past_female': 'сделала',
        'verb_present': 'делает', 'verb_future': 'сделает',
        'display_name': 'Ненормова'
    },
}

# ===== ПРОМПТЫ =====
style_prompts = {
    'streamer': """
Ты — уставший мужик лет 35-40, работяга. Сидишь вечером с пивом, смотришь стримеров и ржешь с них. Твой стиль — как в гараже с мужиками: грубо, с матом, но с юмором.

Напиши короткий пост про стримера/стримеров. Пост должен быть живым, эмоциональным, с реальными историями и наблюдениями.

⚠️ ПРАВИЛА ИСПОЛЬЗОВАНИЯ ПАДЕЖЕЙ (ЭТО ВАЖНО!):
- Вудуш: у Вудуша, Вудушу, Вудушем, о Вудуше
- Праден: у Прадена, Прадену, Праденом, о Прадене
- Братишкин: у Братишкина, Братишкину, Братишкиным, о Братишкине
- Сасавот: у Сасавота, Сасавоту, Сасавотом, о Сасавоте
- Алина Рин: у Алины Рин, Алине Рин, Алиной Рин, об Алине Рин (ОНА!)
- Ласка: у Ласки, Ласке, Лаской, о Ласке
- Аравудус: у Аравудуса, Аравудусу, Аравудусом, о Аравудусе
- Эвелон: у Эвелона, Эвелону, Эвелоном, о Эвелоне
- Бустер: у Бустера, Бустеру, Бустером, о Бустере
- Ненормова: у Ненормовой, Ненормовой, Ненормову, о Ненормовой (ОНА! дворняга)

Требования:
- Пост должен быть 600-900 символов
- Мат 2-5 раз
- Обязательно используй 1-2 локальных мема про стримера
- Используй правильные падежи!
- Острые шутки с юмором
- Используй "так называемый/ая/ые" с иронией
- Не называй своё имя
- Обращайся к читателям на "вы"
""",
    'asia': """
Ты — уставший мужик, работяга. Иногда вспоминаешь про Азию, где всё по-другому. Напиши короткий пост про Азию с юмором и самоиронией.

Требования:
- Пост должен быть 600-900 символов
- Мат 1-2 раза
- Острая шутка с юмором
- Используй "так называемый/ая/ые" с иронией
- Не называй своё имя
- Обращайся к читателям на "вы"
""",
}

# ===== КЛЮЧЕВЫЕ СЛОВА ДЛЯ ПОИСКА =====
STREAMER_QUERIES = {
    'voodoosh': [
        "вудуш на стриме", "voodoosh стрим", "вудуш стример", 
        "вудуш лицо", "voodoosh stream", "вудуш фото"
    ],
    'praden': [
        "праден на стриме", "praden стрим", "праден стример",
        "праден лицо", "praden stream", "праден фото"
    ],
    'bratishkinoff': [
        "братишкин на стриме", "bratishkinoff стрим", "братишкин стример",
        "братишкин лицо", "bratishkinoff stream", "вова братишкин"
    ],
    'sasavot': [
        "сасавот на стриме", "sasavot стрим", "сасавот стример",
        "сасавот лицо", "sasavot stream", "сасавот фото"
    ],
    'alina_rin': [
        "алина рин на стриме", "alina rin стрим", "алина рин стример",
        "алина рин лицо", "alina rin stream", "алина рин фото"
    ],
    'lasqa': [
        "ласка на стриме", "lasqa стрим", "ласка стример",
        "ласка лицо", "lasqa stream", "ласка фото"
    ],
    'arrowwoods': [
        "аравудус на стриме", "arrowwoods стрим", "аравудус стример",
        "аравудус лицо", "arrowwoods stream", "аравудус фото"
    ],
    'evelone': [
        "эвелон на стриме", "evelone стрим", "эвелон стример",
        "эвелон лицо", "evelone stream", "эвелон фото"
    ],
    'buster': [
        "бустер на стриме", "buster стрим", "бустер стример",
        "бустер лицо", "buster stream", "бустер фото"
    ],
    'nenormova': [
        "ненормова на стриме", "nenormova стрим", "ненормова стример",
        "ненормова лицо", "nenormova stream", "ненормова фото",
        "галя ненормова", "ульяна ненормова"
    ],
}

# ===== СПИСКИ ДЛЯ ИМПОРТА =====
# STREAMER_KEYS — для обратной совместимости с media.py
STREAMER_KEYS = [
    'voodoosh', 'praden', 'bratishkinoff', 'sasavot', 'alina_rin',
    'lasqa', 'arrowwoods', 'evelone', 'buster', 'nenormova'
]

# ===== ОТОБРАЖАЕМЫЕ ИМЕНА =====
STREAMER_DISPLAY_NAMES = {
    'voodoosh': 'Вудуш',
    'praden': 'Праден',
    'bratishkinoff': 'Братишкин',
    'sasavot': 'Сасавот',
    'alina_rin': 'Алина Рин',
    'lasqa': 'Ласка',
    'arrowwoods': 'Аравудус',
    'evelone': 'Эвелон',
    'buster': 'Бустер',
    'nenormova': 'Ненормова',
}

# ===== ФУНКЦИИ =====
def get_streamer_for_post() -> Tuple[str, str]:
    """Возвращает случайного стримера (ключ, отображаемое имя)."""
    key = random.choice(STREAMER_KEYS)
    return key, STREAMER_DISPLAY_NAMES[key]

def get_streamer_display_name(streamer_key: str) -> str:
    """Отображаемое имя стримера по ключу."""
    return STREAMER_DISPLAY_NAMES.get(streamer_key, streamer_key)

# ===== ЗАПРОСЫ ДЛЯ ПОСТОВ ПРО АЗИЮ =====
ASIAN_QUERIES = [
    "japanese idol girl portrait",
    "kpop girl group member photo",
    "korean idol female portrait",
    "asian model girl portrait",
    "japanese girl idol photo",
    "kpop female idol face",
    "asian woman model portrait",
    "korean girl idol photo shoot",
]
