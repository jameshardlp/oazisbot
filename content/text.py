"""Функции для обработки текста: очистка, валидация, обрезка."""
import re
import logging
from typing import Tuple, List

logger = logging.getLogger(__name__)

# Хранилище последних постов (для избежания повторов)
_last_posts = []


def clean_text(text: str) -> str:
    """
    Очищает текст от лишних символов и форматирует его.
    """
    if not text:
        return ""
    
    # Убираем множественные пробелы
    text = re.sub(r'\s+', ' ', text)
    
    # Убираем пробелы перед знаками препинания
    text = re.sub(r'\s+([.,!?;:])', r'\1', text)
    
    # Убираем лишние кавычки в начале и конце
    text = text.strip().strip('"').strip("'")
    
    # Исправляем тире
    text = text.replace(' - ', ' — ').replace(' -', ' — ')
    
    return text.strip()


def validate_caption(text: str, min_length: int = 50, max_length: int = 300) -> Tuple[bool, str]:
    """
    Проверяет текст поста на соответствие требованиям.
    
    Args:
        text: Текст для проверки
        min_length: Минимальная длина
        max_length: Максимальная длина
        
    Returns:
        (валидность, сообщение_об_ошибке)
    """
    if not text:
        return False, "Текст пустой"
    
    if len(text) < min_length:
        return False, f"Слишком короткий ({len(text)} символов, нужно минимум {min_length})"
    
    if len(text) > max_length:
        return False, f"Слишком длинный ({len(text)} символов, максимум {max_length})"
    
    # Проверяем, что текст не состоит только из ссылок
    if re.match(r'^https?://\S+$', text.strip()):
        return False, "Текст содержит только ссылку"
    
    return True, "OK"


def truncate_by_sentences(text: str, max_length: int) -> str:
    """
    Обрезает текст до максимальной длины, сохраняя целостность предложений.
    """
    if len(text) <= max_length:
        return text
    
    # Ищем конец последнего полного предложения в пределах max_length
    truncated = text[:max_length]
    
    # Ищем последний знак конца предложения
    last_period = truncated.rfind('.')
    last_exclamation = truncated.rfind('!')
    last_question = truncated.rfind('?')
    
    last_end = max(last_period, last_exclamation, last_question)
    
    if last_end > max_length // 2:  # Если нашли хороший конец предложения
        return truncated[:last_end + 1].strip()
    else:
        # Если нет хорошего конца, обрезаем по последнему пробелу
        last_space = truncated.rfind(' ')
        if last_space > max_length // 2:
            return truncated[:last_space].strip() + '...'
        else:
            return truncated.strip() + '...'


def add_to_last_posts(text: str, max_posts: int = 10) -> None:
    """
    Добавляет текст в список последних постов.
    """
    global _last_posts
    
    _last_posts.append(text)
    if len(_last_posts) > max_posts:
        _last_posts.pop(0)


def get_last_posts(count: int = 5) -> List[str]:
    """
    Возвращает последние N постов.
    """
    return _last_posts[-count:] if _last_posts else []


def is_duplicate(text: str, threshold: float = 0.8) -> bool:
    """
    Проверяет, не является ли текст дубликатом существующих постов.
    Использует простое сравнение — процент совпадения слов.
    """
    if not _last_posts:
        return False
    
    text_words = set(text.lower().split())
    
    for post in _last_posts:
        post_words = set(post.lower().split())
        
        # Если оба пустые
        if not text_words or not post_words:
            continue
        
        # Вычисляем пересечение
        common = text_words.intersection(post_words)
        similarity = len(common) / max(len(text_words), len(post_words))
        
        if similarity > threshold:
            logger.info(f"⚠️ Обнаружен дубликат! Похожесть: {similarity:.2f}")
            return True
    
    return False
