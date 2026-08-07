"""Очистка, обрезка и валидация текста постов."""
import re
from typing import Optional, Tuple

# Последние посты — для проверки на самоповтор
last_posts = []

def clean_punctuation(text: str) -> str:
    if not text:
        return ''
    text = re.sub(r'[.!?]{2,}', '.', text)
    text = re.sub(r'\s+', ' ', text)
    text = text.replace('«', '"').replace('»', '"')
    text = text.replace('„', '"').replace('“', '"')
    text = text.replace('`', "'").replace('´', "'")
    text = re.sub(r'[()\[\]{}<>]', '', text)
    text = re.sub(r',\s*\.', '.', text)
    return text.strip()

def ensure_ends_with_dot(text: str) -> str:
    """Обрезает текст до последнего завершённого предложения.

    Имя историческое: точка не дописывается, а отбрасывается «хвост»
    после последнего .!?
    """
    text = (text or '').strip()
    if not text:
        return ''
    if text[-1] in '.!?':
        return text
    last_end = max(text.rfind('.'), text.rfind('!'), text.rfind('?'))
    if last_end != -1:
        return text[:last_end + 1].strip()
    return text

def get_sentences(text: str) -> list:
    if not text:
        return []
    return re.split(r'(?<=[.!?])\s+', text.strip())

# Глаголы для проверки коротких предложений (<=20 символов)
SHORT_SENTENCE_VERBS = [
    'быть', 'стать', 'являться', 'иметь', 'делать', 'сказать', 'пойти',
    'знать', 'думать', 'смотреть', 'видеть', 'слышать', 'чувствовать',
    'понимать', 'хотеть', 'мочь', 'бывать', 'начинать', 'продолжать',
    'заканчивать', 'становиться', 'оставаться', 'казаться', 'стоить',
    'говорить', 'идти', 'стоять', 'сидеть', 'лежать', 'бежать',
    'плыть', 'лететь', 'ехать', 'работать', 'учиться', 'читать',
    'писать', 'рисовать', 'петь', 'танцевать', 'играть', 'смотреть',
    'слушать', 'дышать', 'жить', 'умирать', 'родиться', 'расти',
    'помнить', 'забывать', 'любить', 'ненавидеть', 'мечтать',
    'получаться', 'получиться', 'случаться', 'случиться', 'происходить',
    'произойти', 'существовать', 'обладать', 'пользоваться', 'управлять',
    'думаю', 'знаю', 'понимаю', 'вижу', 'слышу', 'чувствую'
]

def is_sentence_complete(sentence: str) -> bool:
    if not sentence:
        return False
    clean = re.sub(r'[.!?]$', '', sentence).strip()
    words = clean.split()
    if len(words) < 2:
        return False
    incomplete_words = ['и', 'а', 'но', 'да', 'или', 'либо', 'за', 'перед', 'под', 'над', 'без', 'для', 'про', 'через', 'между', 'среди', 'у', 'о', 'об', 'от', 'до', 'из', 'с', 'к', 'по', 'на', 'в', 'во', 'вот', 'тем', 'того', 'этого', 'того']
    last_word = words[-1].lower()
    if last_word in incomplete_words:
        return False
    incomplete_endings = [
        'в её глазах', 'в моей голове', 'в моих мыслях', 'в моей душе',
        'в моём сердце', 'в моей жизни', 'в моём мире', 'в его глазах',
        'в её голове', 'в моём сознании', 'в моей памяти', 'в моих мечтах',
        'на его лице', 'на её лице', 'в моём воображении',
        'и вы знаете', 'и я понимаю', 'и мне кажется', 'и я думаю',
        'но вы понимаете', 'но я знаю', 'и вы понимаете',
        'и я чувствую', 'и я понимаю, что', 'и я думаю, что',
        'я начинаю', 'я продолжаю', 'я хочу сказать', 'я хочу отметить',
        'я думаю о том', 'я говорю о том', 'я говорю про', 'я думаю про',
        'в общем', 'короче говоря', 'так что', 'поэтому',
        'в темноте', 'в тем', 'на тем', 'в том', 'о том',
        'и я', 'но я', 'а я', 'что я', 'когда я', 'пока я',
        'она берет', 'он берет', 'они берут', 'я беру', 'ты берешь',
        'упа', 'будто', 'как', 'словно', 'точно', 'прямо', 'почти'
    ]
    clean_lower = clean.lower()
    for ending in incomplete_endings:
        if clean_lower.endswith(ending):
            return False
    incomplete_adverbs = ['тогда', 'потом', 'сейчас', 'здесь', 'там', 'тут', 'вчера', 'сегодня', 'завтра', 'всегда', 'никогда', 'иногда', 'уже', 'ещё', 'просто', 'даже', 'почти', 'совсем', 'очень', 'слишком', 'также', 'тоже']
    if last_word in incomplete_adverbs and len(words) < 5:
        return False
    # Длинное предложение считаем завершённым. Разбор на глагол+подлежащее
    # нужен только для коротких огрызков.
    if len(clean) > 20:
        return True
    has_verb = any(verb in clean_lower for verb in SHORT_SENTENCE_VERBS)
    has_subject = bool(re.search(r'\b(я|ты|он|она|оно|мы|вы|они|это|тот|всё|все|кто|что|который|которые|которое|эта|этот|эти|сам|себя)\b', clean, re.IGNORECASE))
    return has_verb and has_subject

# Полный дубль ensure_ends_with_dot — оставлен как псевдоним для читаемости
drop_incomplete_tail = ensure_ends_with_dot

def truncate_by_sentences(text: str, max_length: int = 900) -> str:
    if not text:
        return ''
    text = text.strip()
    text = drop_incomplete_tail(text)
    if len(text) <= max_length:
        return ensure_ends_with_dot(text)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    result = []
    current_length = 0
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if current_length + len(sentence) + 1 <= max_length:
            result.append(sentence)
            current_length += len(sentence) + 1
        else:
            break
    if not result and sentences:
        first = sentences[0].strip()
        if len(first) <= max_length:
            result.append(first)
    final_text = ' '.join(result).strip()
    if final_text:
        final_text = ensure_ends_with_dot(final_text)
    return final_text

def clean_text(text: str) -> str:
    if not text:
        return ''
    text = text.replace('—', '-').replace('–', '-')
    text = text.replace('@maddysontg', '').replace('@Maddysontg', '').replace('@MADDYSONTG', '')
    text = text.replace('maddysontg', '').replace('Maddysontg', '').replace('MADDYSONTG', '')
    text = re.sub(r'\s+', ' ', text).strip()
    text = clean_punctuation(text)
    return text

def validate_caption(text: str, min_length: int = 600, max_length: int = 900) -> Tuple[str, Optional[str]]:
    """Проверяет текст с ограничениями по длине 600-900 символов"""
    if not text:
        return '', 'Текст пустой'
    text = clean_text(text)
    if len(text) < 10:
        return '', 'Слишком короткий (меньше 10 символов)'
    if len(text) > max_length:
        text = truncate_by_sentences(text, max_length)
        if not text:
            return '', 'Текст слишком длинный и не может быть обрезан'
    if len(text) < min_length:
        return '', f'Слишком короткий ({len(text)} символов, нужно {min_length})'
    if not text.endswith(('.', '!', '?')):
        text = ensure_ends_with_dot(text)
    all_sentences = get_sentences(text)
    if not all_sentences:
        return '', 'Нет предложений'
    last_sentence = all_sentences[-1].strip() if all_sentences else ''
    if last_sentence:
        if not last_sentence.endswith(('.', '!', '?')):
            if len(all_sentences) > 1:
                text = ' '.join(all_sentences[:-1]).strip()
                text = ensure_ends_with_dot(text)
            else:
                return '', 'Последнее предложение не завершено'
        word_count = len(last_sentence.split())
        if word_count < 3:
            if len(all_sentences) > 1:
                text = ' '.join(all_sentences[:-1]).strip()
                text = ensure_ends_with_dot(text)
            else:
                return '', f'Последнее предложение слишком короткое ({word_count} слов)'
        if not is_sentence_complete(last_sentence):
            if len(all_sentences) > 1:
                text = ' '.join(all_sentences[:-1]).strip()
                text = ensure_ends_with_dot(text)
            else:
                return '', 'Последнее предложение не завершено логически'
    return text, None

def add_to_last_posts(text: str):
    global last_posts
    if not text or len(text) < 10:
        return
    key = text[:100]
    last_posts.append(key)
    if len(last_posts) > 20:
        last_posts.pop(0)

def is_similar(text: str) -> bool:
    global last_posts
    if not text:
        return False
    key = text[:150]
    for post in last_posts:
        same_chars = sum(1 for a, b in zip(key, post) if a == b)
        if len(key) > 10 and same_chars / len(key) > 0.70:
            return True
    return False
