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
    'nenormova': {
        'name': 'Ненормова', 'gender': 'female', 'nominative': 'Ненормова',
        'genitive': 'Ненормовой', 'dative': 'Ненормовой', 'accusative': 'Ненормову',
        'instrumental': 'Ненормовой', 'prepositional': 'Ненормовой',
        'pronoun': 'она', 'possessive': 'её',
        'verb_past_male': 'сделала', 'verb_past_female': 'сделала',
        'verb_present': 'делает', 'verb_future': 'сделает',
        'display_name': 'Ненормова'
    },
    't2x2': {
        'name': 'T2x2', 'gender': 'male', 'nominative': 'T2x2',
        'genitive': 'T2x2', 'dative': 'T2x2', 'accusative': 'T2x2',
        'instrumental': 'T2x2', 'prepositional': 'T2x2',
        'pronoun': 'он', 'possessive': 'его',
        'verb_past_male': 'сделал', 'verb_past_female': 'сделала',
        'verb_present': 'делает', 'verb_future': 'сделает',
        'display_name': 'T2x2'
    },
    'dinablin': {
        'name': 'Дина Блин', 'gender': 'female', 'nominative': 'Дина Блин',
        'genitive': 'Дины Блин', 'dative': 'Дине Блин', 'accusative': 'Дину Блин',
        'instrumental': 'Диной Блин', 'prepositional': 'Дине Блин',
        'pronoun': 'она', 'possessive': 'её',
        'verb_past_male': 'сделала', 'verb_past_female': 'сделала',
        'verb_present': 'делает', 'verb_future': 'сделает',
        'display_name': 'Дина Блин'
    },
    'olyashaa': {
        'name': 'Оляша', 'gender': 'female', 'nominative': 'Оляша',
        'genitive': 'Оляши', 'dative': 'Оляше', 'accusative': 'Оляшу',
        'instrumental': 'Оляшей', 'prepositional': 'Оляше',
        'pronoun': 'она', 'possessive': 'её',
        'verb_past_male': 'сделала', 'verb_past_female': 'сделала',
        'verb_present': 'делает', 'verb_future': 'сделает',
        'display_name': 'Оляша'
    },
    'guit88man': {
        'name': 'Гитман', 'gender': 'male', 'nominative': 'Гитман',
        'genitive': 'Гитмана', 'dative': 'Гитману', 'accusative': 'Гитмана',
        'instrumental': 'Гитманом', 'prepositional': 'Гитмане',
        'pronoun': 'он', 'possessive': 'его',
        'verb_past_male': 'сделал', 'verb_past_female': 'сделала',
        'verb_present': 'делает', 'verb_future': 'сделает',
        'display_name': 'Гитман'
    },
    'recrent': {
        'name': 'Рекрент', 'gender': 'male', 'nominative': 'Рекрент',
        'genitive': 'Рекрента', 'dative': 'Рекренту', 'accusative': 'Рекрента',
        'instrumental': 'Рекрентом', 'prepositional': 'Рекренте',
        'pronoun': 'он', 'possessive': 'его',
        'verb_past_male': 'сделал', 'verb_past_female': 'сделала',
        'verb_present': 'делает', 'verb_future': 'сделает',
        'display_name': 'Рекрент'
    },
    'koryamc': {
        'name': 'Коря МС', 'gender': 'female', 'nominative': 'Коря МС',
        'genitive': 'Кори МС', 'dative': 'Коре МС', 'accusative': 'Корю МС',
        'instrumental': 'Корей МС', 'prepositional': 'Коре МС',
        'pronoun': 'она', 'possessive': 'её',
        'verb_past_male': 'сделала', 'verb_past_female': 'сделала',
        'verb_present': 'делает', 'verb_future': 'сделает',
        'display_name': 'Коря МС'
    },
    'karmikkoala': {
        'name': 'Кармик', 'gender': 'male', 'nominative': 'Кармик',
        'genitive': 'Кармика', 'dative': 'Кармику', 'accusative': 'Кармика',
        'instrumental': 'Кармиком', 'prepositional': 'Кармике',
        'pronoun': 'он', 'possessive': 'его',
        'verb_past_male': 'сделал', 'verb_past_female': 'сделала',
        'verb_present': 'делает', 'verb_future': 'сделает',
        'display_name': 'Кармик'
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
- Аравудус: у Аравудуса, Аравудусу, Аравудусом, о Аравудусе
- Эвелон: у Эвелона, Эвелону, Эвелоном, о Эвелоне
- Бустер: у Бустера, Бустеру, Бустером, о Бустере
- Ненормова: у Ненормовой, Ненормовой, Ненормову, о Ненормовой (ОНА! дворняга)
- T2x2: у T2x2, T2x2, T2x2, о T2x2 (Тоха)
- Дина Блин: у Дины Блин, Дине Блин, Дину Блин, о Дине Блин (ОНА!)
- Оляша: у Оляши, Оляше, Оляшу, об Оляше (ОНА! пожилая)
- Гитман: у Гитмана, Гитману, Гитманом, о Гитмане
- Рекрент: у Рекрента, Рекренту, Рекрентом, о Рекренте
- Коря МС: у Кори МС, Коре МС, Корю МС, о Коре МС (ОНА!)
- Кармик: у Кармика, Кармику, Кармиком, о Кармике

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
    't2x2': [
        "t2x2 стрим", "тоха стрим", "t2x2 стример",
        "t2x2 фото", "тоха фото"
    ],
    'dinablin': [
        "дина блин стрим", "dinablin стрим", "дина блин стример",
        "дина блин фото", "dinablin фото"
    ],
    'olyashaa': [
        "оляша стрим", "olyashaa стрим", "оляша стример",
        "оляша фото", "olyashaa фото"
    ],
    'guit88man': [
        "гитман стрим", "guit88man стрим", "гитман стример",
        "гитман фото", "guit88man фото"
    ],
    'recrent': [
        "рекрент стрим", "recrent стрим", "рекрент стример",
        "рекрент фото", "recrent фото"
    ],
    'koryamc': [
        "коря мс стрим", "koryamc стрим", "коря мс стример",
        "коря мс фото", "koryamc фото"
    ],
    'karmikkoala': [
        "кармик стрим", "karmikkoala стрим", "кармик стример",
        "кармик фото", "karmikkoala фото"
    ],
}

# ===== СПИСКИ ДЛЯ ИМПОРТА =====
STREAMER_KEYS = [
    'voodoosh', 'praden', 'bratishkinoff', 'sasavot', 'alina_rin',
    'arrowwoods', 'evelone', 'buster', 'nenormova',
    't2x2', 'dinablin', 'olyashaa', 'guit88man', 'recrent', 'koryamc', 'karmikkoala'
]

# ===== ОТОБРАЖАЕМЫЕ ИМЕНА =====
STREAMER_DISPLAY_NAMES = {
    'voodoosh': 'Вудуш',
    'praden': 'Праден',
    'bratishkinoff': 'Братишкин',
    'sasavot': 'Сасавот',
    'alina_rin': 'Алина Рин',
    'arrowwoods': 'Аравудус',
    'evelone': 'Эвелон',
    'buster': 'Бустер',
    'nenormova': 'Ненормова',
    't2x2': 'T2x2',
    'dinablin': 'Дина Блин',
    'olyashaa': 'Оляша',
    'guit88man': 'Гитман',
    'recrent': 'Рекрент',
    'koryamc': 'Коря МС',
    'karmikkoala': 'Кармик',
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
