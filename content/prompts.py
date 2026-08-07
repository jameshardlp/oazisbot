"""Сборка и кэширование промптов для DeepSeek."""
import logging

from streamers import STREAMER_INFO, style_prompts

logger = logging.getLogger(__name__)

_system_prompt_cache = {}

def get_system_prompt() -> str:
    cache_key = "system_prompt_v4"
    if cache_key not in _system_prompt_cache:
        _system_prompt_cache[cache_key] = """Ты — уставший мужик лет 35-40, работяга. Сидишь вечером с пивом, смотришь стримеров и ржешь с них.

⚠️ ПРАВИЛА РУССКОГО ЯЗЫКА:
1. Все стримеры (кроме Алины Рин) — МУЖСКОГО РОДА. Используй: он, его, ему, им, нём.
2. Алина Рин — ЖЕНСКОГО РОДА. Используй: она, её, ей, ей, ней.
3. Падежи для мужских имён:
   - Вудуш → у Вудуша, Вудушу, Вудушем, о Вудуше
   - Праден → у Прадена, Прадену, Праденом, о Прадене
   - Братишкин → у Братишкина, Братишкину, Братишкиным, о Братишкине
   - Сасавот → у Сасавота, Сасавоту, Сасавотом, о Сасавоте
   - Ласка → у Ласки, Ласке, Лаской, о Ласке
   - Аравудус → у Аравудуса, Аравудусу, Аравудусом, о Аравудусе
   - Эвелон → у Эвелона, Эвелону, Эвелоном, о Эвелоне
   - Бустер → у Бустера, Бустеру, Бустером, о Бустере
4. Падежи для женских имён:
   - Алина Рин → у Алины Рин, Алине Рин, Алиной Рин, об Алине Рин

Отвечай ТОЛЬКО готовым постом. БЕЗ РАССУЖДЕНИЙ."""
        logger.info("💾 Системный промпт закэширован")
    return _system_prompt_cache[cache_key]

def get_style_prompt(style: str, streamer_key: str = None) -> str:
    cache_key = f"style_prompt_{style}_{streamer_key}"
    
    if cache_key not in _system_prompt_cache:
        base_prompt = style_prompts.get(style, style_prompts['streamer'])
        
        if streamer_key and streamer_key in STREAMER_INFO:
            info = STREAMER_INFO[streamer_key]
            name = info['name']
            pronoun = info['pronoun']
            genitive = info['genitive']
            dative = info['dative']
            accusative = info['accusative']
            instrumental = info['instrumental']
            prepositional = info['prepositional']
            
            gender_hint = f"""
⚠️ ВАЖНО! СТРИМЕР {name} — {pronoun.upper()}

Правильные падежи для {name}:
- Именительный: {name}
- Родительный: {genitive}
- Дательный: {dative}
- Винительный: {accusative}
- Творительный: {instrumental}
- Предложный: {prepositional}
"""
            _system_prompt_cache[cache_key] = gender_hint + base_prompt + """

⚠️ ВАЖНО: Пиши строго по теме. Без рассуждений. Только готовый пост.
Твой ответ (ТОЛЬКО ПОСТ, БЕЗ РАССУЖДЕНИЙ):"""
        else:
            _system_prompt_cache[cache_key] = base_prompt + """

⚠️ ВАЖНО: Пиши строго по теме. Без рассуждений. Только готовый пост.
Твой ответ (ТОЛЬКО ПОСТ, БЕЗ РАССУЖДЕНИЙ):"""
        
        logger.info(f"💾 Промпт для стиля {style} закэширован")
    
    return _system_prompt_cache[cache_key]

def clear_prompt_cache():
    global _system_prompt_cache
    _system_prompt_cache.clear()
    logger.info("🗑️ Кэш промптов очищен")
