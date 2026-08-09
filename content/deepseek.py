"""Генерация текста поста через DeepSeek.

generate_caption_with_validation делает до 20 попыток: генерация -> чистка ->
проверка длины 50-300 -> валидация -> модерация вторым запросом. При полном
провале возвращает пустую строку (не заглушку), чтобы вызывающий код это увидел.
"""
import logging
import random
import time
import requests
import re
import asyncio
from typing import Optional, Tuple, List
from datetime import datetime, timedelta

from config import DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_API_URL
from content.prompts import get_system_prompt, get_style_prompt
from content.streamers import STREAMER_INFO, get_streamer_for_post
from content.text import clean_text, validate_caption, truncate_by_sentences, add_to_last_posts

# ID канала maddysontg для чтения стиля
MADDYSON_CHANNEL_ID = -1001769375081

# Настройки для Pyrogram
try:
    from pyrogram import Client
    from pyrogram.errors import RPCError
    PYROGRAM_AVAILABLE = True
except ImportError:
    PYROGRAM_AVAILABLE = False
    logging.warning("⚠️ Pyrogram не установлен. Чтение канала недоступно.")

logger = logging.getLogger(__name__)

# Глобальный кэш для постов из канала
_cached_posts = []
_cache_time = 0
CACHE_TTL = 3600  # Обновлять раз в час

# Pyrogram клиент (глобальный)
_pyrogram_client = None

def init_pyrogram_client(api_id: int, api_hash: str, session_name: str = "maddyson_reader"):
    """
    Инициализирует Pyrogram клиент.
    Вызывать один раз при старте бота.
    """
    global _pyrogram_client
    
    if not PYROGRAM_AVAILABLE:
        logger.error("❌ Pyrogram не установлен!")
        return None
    
    if _pyrogram_client is None:
        _pyrogram_client = Client(
            session_name,
            api_id=api_id,
            api_hash=api_hash,
            in_memory=True  # Не сохраняем сессию на диск
        )
        logger.info("✅ Pyrogram клиент инициализирован")
    
    return _pyrogram_client

def get_posts_from_channel(limit: int = 5, force_refresh: bool = False) -> List[str]:
    """
    Получает последние посты из канала maddysontg.
    Использует кэш, чтобы не дёргать API каждый раз.
    """
    global _cached_posts, _cache_time
    
    current_time = time.time()
    
    # Если кэш ещё свежий и не требуется принудительное обновление — возвращаем его
    if not force_refresh and _cached_posts and (current_time - _cache_time) < CACHE_TTL:
        logger.info(f"📦 Использую кэш ({len(_cached_posts)} постов)")
        return _cached_posts
    
    # Если Pyrogram не установлен — используем заглушку
    if not PYROGRAM_AVAILABLE:
        logger.warning("⚠️ Pyrogram не установлен, использую заглушку")
        posts = get_default_style_examples()
        _cached_posts = posts
        _cache_time = current_time
        return posts
    
    # Если клиент не инициализирован — используем заглушку
    if _pyrogram_client is None:
        logger.warning("⚠️ Pyrogram клиент не инициализирован, использую заглушку")
        posts = get_default_style_examples()
        _cached_posts = posts
        _cache_time = current_time
        return posts
    
    try:
        logger.info(f"📖 Читаю посты из канала maddysontg (CHANNEL_ID: {MADDYSON_CHANNEL_ID})...")
        
        # Запускаем асинхронную функцию синхронно
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            posts = loop.run_until_complete(_async_fetch_posts(limit))
        finally:
            loop.close()
        
        if posts:
            _cached_posts = posts
            _cache_time = current_time
            logger.info(f"✅ Загружено {len(posts)} постов из канала")
        else:
            logger.warning("⚠️ Не удалось загрузить посты из канала, использую заглушку")
            posts = get_default_style_examples()
            _cached_posts = posts
            _cache_time = current_time
        
        return _cached_posts
        
    except Exception as e:
        logger.error(f"❌ Ошибка при получении постов из канала: {e}")
        posts = get_default_style_examples()
        _cached_posts = posts
        _cache_time = current_time
        return posts

async def _async_fetch_posts(limit: int) -> List[str]:
    """
    Асинхронная функция для получения постов из канала через Pyrogram.
    """
    if _pyrogram_client is None:
        return []
    
    posts = []
    
    try:
        # Запускаем клиент
        await _pyrogram_client.start()
        
        logger.info(f"📖 Читаю {limit} последних постов из канала...")
        
        # Получаем историю сообщений
        # Сообщения приходят в обратном порядке (сначала новые)
        async for message in _pyrogram_client.get_chat_history(
            chat_id=MADDYSON_CHANNEL_ID,
            limit=limit
        ):
            # Проверяем, что это текстовое сообщение и оно не пустое
            if message.text and len(message.text.strip()) > 20:
                # Очищаем от лишних символов
                clean = message.text.strip()
                posts.append(clean)
                logger.debug(f"📝 Пост: {clean[:50]}...")
        
        # Если постов мало, пытаемся взять ещё (с запасом)
        if len(posts) < 3:
            logger.info(f"📖 Получено только {len(posts)} постов, пробую взять больше...")
            # Берём больше постов чтобы было из чего выбрать
            async for message in _pyrogram_client.get_chat_history(
                chat_id=MADDYSON_CHANNEL_ID,
                limit=limit * 3
            ):
                if message.text and len(message.text.strip()) > 20:
                    clean = message.text.strip()
                    if clean not in posts:  # Избегаем дубликатов
                        posts.append(clean)
                    if len(posts) >= limit * 2:  # Берём в 2 раза больше чем нужно
                        break
        
        await _pyrogram_client.stop()
        
    except RPCError as e:
        logger.error(f"❌ RPC ошибка при чтении канала: {e}")
    except Exception as e:
        logger.error(f"❌ Ошибка при чтении канала: {e}")
    
    return posts[:limit]  # Возвращаем ровно столько, сколько запрошено

def get_default_style_examples() -> List[str]:
    """Возвращает примеры стиля на случай, если канал недоступен."""
    return [
        "Да ну нахуй, этот клоун опять на стриме орёт. Сидел бы лучше в МЧС, чем зрителей за деньги веселить.",
        "Смотрю я на этого блогера и думаю — ну как так можно жить? Накрутил ботов и думает что он король.",
        "Азия — это пиздец. Там такое творится, что я ахерел. Люди живут в каком-то параллельном мире.",
        "Дианочка снова накрутила. Сколько можно? У меня уже крыша едет от этой ботоводки.",
    ]

def get_style_context(limit: int = 3) -> str:
    """
    Формирует контекст стиля из постов канала maddysontg.
    """
    posts = get_posts_from_channel(limit=limit)
    
    if not posts:
        return "Используй мат, чёрный юмор, сарказм и самоиронию. Пиши коротко и ёмко."
    
    # Формируем контекст с примерами
    context = "Вот примеры постов в стиле, котором нужно писать:\n\n"
    for i, post in enumerate(posts[:limit], 1):
        context += f"Пример {i}:\n{post}\n\n"
    
    context += "Пиши в ТОЧНО таком же стиле: мат, чёрный юмор, сарказм, самоирония, короткие предложения. Используй ту же лексику и манеру изложения."
    
    return context

def request_continuation(previous_text: str) -> str:
    if not DEEPSEEK_API_KEY:
        return ""
    try:
        url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        tail = previous_text[-500:]
        data = {
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": "Ты уставший мужик. Текст поста был обрезан. Допиши ТОЛЬКО концовку — 1-3 завершающих предложения с логическим выводом. Не повторяй уже написанное. Только текст продолжения."},
                {"role": "user", "content": f"Вот текст, который оборвался:\n\n...{tail}\n\nДопиши концовку (1-3 предложения)."}
            ],
            "temperature": 0.9,
            "max_tokens": 200,
        }
        response = requests.post(url, headers=headers, json=data, timeout=30)
        if response.status_code == 200:
            result = response.json()
            if result.get("choices") and len(result["choices"]) > 0:
                return result["choices"][0].get("message", {}).get("content", "").strip()
    except Exception as e:
        logger.error(f"Ошибка запроса продолжения: {e}")
    return ""

def validate_post_with_deepseek(post_text: str) -> Tuple[bool, str]:
    if not DEEPSEEK_API_KEY:
        logger.warning("⚠️ Нет DeepSeek API ключа для проверки поста")
        return True, post_text
    
    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": """Ты — строгий модератор контента. Проверяй посты на соответствие правилам:

1. Пост должен быть о стримерах или Азии (по теме)
2. Допускается грубая лексика и мат (это стиль автора)
3. Пост должен быть грамотным
4. Пост должен быть завершённым
5. Пост должен быть 50-300 символов
6. Пост должен иметь минимум 2 абзаца
7. Пост НЕ должен содержать фраз типа "сижу", "вчера сидел", "пиво пью", "листаю стрим" и других унылых выражений
8. Пост должен быть похож на комментарий к фото/видео

Если пост соответствует — напиши "APPROVED".
Если пост НЕ соответствует — напиши "REJECT: причина"."""},
                {"role": "user", "content": f"Проверь этот пост:\n\n{post_text}"}
            ],
            "temperature": 0.3,
            "max_tokens": 100,
        }
        
        response = requests.post(
            DEEPSEEK_API_URL,
            headers=headers,
            json=data,
            timeout=15
        )
        
        if response.status_code == 200:
            result = response.json()
            verdict = result["choices"][0]["message"]["content"].strip()
            
            if verdict.startswith("APPROVED"):
                logger.info("✅ Пост прошёл проверку DeepSeek")
                return True, post_text
            elif verdict.startswith("REJECT:"):
                reason = verdict.replace("REJECT:", "").strip()
                logger.warning(f"❌ Пост отклонён: {reason}")
                return False, reason
            else:
                logger.warning(f"⚠️ Неизвестный ответ DeepSeek: {verdict}")
                return True, post_text
        else:
            logger.error(f"❌ Ошибка проверки поста: {response.status_code}")
            return True, post_text
            
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке поста через DeepSeek: {e}")
        return True, post_text

def count_paragraphs(text: str) -> int:
    """Подсчитывает количество абзацев в тексте."""
    if '\n\n' in text:
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        if len(paragraphs) >= 2:
            return len(paragraphs)
    
    if '\n' in text:
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
        if len(paragraphs) >= 2:
            return len(paragraphs)
    
    sentences = re.split(r'[.!?]\s+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
    
    if len(sentences) >= 2:
        return min(3, len(sentences) // 2 + 1)
    
    return 1

def has_banned_phrases(text: str) -> Tuple[bool, str]:
    """Проверяет наличие запрещённых фраз в тексте."""
    banned_phrases = [
        # Унылые фразы про сидение
        (r'сижу\s+вот', 'сижу вот'),
        (r'сижу\s+и\s+п[ию]?[ю]?', 'сижу и'),
        (r'вчера\s+сидел', 'вчера сидел'),
        (r'сидел\s+вчера', 'сидел вчера'),
        (r'сижу\s+сейчас', 'сижу сейчас'),
        (r'сейчас\s+сижу', 'сейчас сижу'),
        
        # Унылые фразы про пиво
        (r'пиво\s+пью', 'пиво пью'),
        (r'пью\s+пиво', 'пью пиво'),
        (r'пивасик', 'пивасик'),
        (r'пивко', 'пивко'),
        
        # Бредовые фразы про стримы
        (r'листаю\s+стрим', 'листаю стрим'),
        (r'листать\s+стрим', 'листать стрим'),
        (r'пролистываю\s+стрим', 'пролистываю стрим'),
        (r'смотрю\s+стрим\s+и\s+листаю', 'смотрю стрим и листаю'),
        
        # Другие унылые фразы
        (r'буду\s+сидеть', 'буду сидеть'),
        (r'посижу', 'посижу'),
        
        # Фразы-паразиты
        (r'короче\s+говор[я]', 'короче говоря'),
        (r'в\s+общем', 'в общем'),
        (r'как\s+бы', 'как бы'),
        (r'типа\s+того', 'типа того'),
        (r'ну\s+это', 'ну это'),
        
        # Фразы которые выдают бота
        (r'я\s+думаю', 'я думаю'),
        (r'мне\s+кажется', 'мне кажется'),
        (r'на\s+мой\s+взгляд', 'на мой взгляд'),
        (r'по\s+моему', 'по моему'),
    ]
    
    text_lower = text.lower()
    for pattern, phrase in banned_phrases:
        if re.search(pattern, text_lower):
            return True, phrase
    
    return False, ""

def generate_caption_with_validation() -> Tuple[str, Optional[str]]:
    """
    Генерирует пост с проверкой.
    Для чтения стиля из канала используется Pyrogram.
    """
    logger.info("Генерирую уникальный пост с проверкой...")
    
    # Получаем стиль из канала maddysontg
    style_context = get_style_context(limit=3)
    
    rand = random.random()
    if rand < 0.85:
        style = 'streamer'
        streamer_key, streamer_display = get_streamer_for_post()
        topic = f"стример {streamer_display}"
        logger.info(f"Генерация поста про {streamer_display}")
    else:
        style = 'asia'
        streamer_key = None
        streamer_display = None
        topic = "Азия"
        logger.info(f"Генерация поста про Азию")
    
    if not DEEPSEEK_API_KEY:
        logger.error("❌ Нет ключа DeepSeek API")
        return "", streamer_key
    
    max_attempts = 20
    for attempt in range(max_attempts):
        try:
            logger.info(f"Попытка {attempt+1}/{max_attempts} для {topic}")
            
            # Базовый промпт со стилем из канала
            base_prompt = f"""{style_context}

Ты — стример-миллионник. Ты смотришь контент и комментируешь его в своём фирменном стиле.
Ты НИКОГДА не упоминаешь, что ты стример.
Твоя главная врагиня — Дианочка, которая занимается ботоводством и накрутками. Она сломала тебе жизнь, увела зрителей и рекламодателей. Ты её ненавидишь.

СТРОГО ЗАПРЕЩЕНО использовать фразы: 'сижу', 'вчера сидел', 'пиво пью', 'листаю стрим', 'я думаю', 'мне кажется'.
Ты не сидишь — ты смотришь контент и комментируешь.
ОБЯЗАТЕЛЬНО раздели пост на 2 абзаца.
Длина: 50-300 символов.
"""
            
            streamer_topics = []
            if streamer_key and streamer_key in STREAMER_INFO:
                info = STREAMER_INFO[streamer_key]
                name = info['name']
                pronoun = info['pronoun']
                genitive = info['genitive']
                dative = info['dative']
                accusative = info['accusative']
                
                streamer_topics = [
                    f"Клип с {name}. Что там происходит? {pronoun} снова позорится? Или Дианочка накрутила {dative} ботов? Напиши короткий комментарий.",
                    f"Ты смотришь клип с {name}. В клипе видно как {pronoun} что-то делает. Опиши это и дай оценку. Критикуй, смейся, используй мат.",
                    f"Клип с участием {name}. Что {pronoun} сделал не так? Или наоборот — красавчик? Используй сарказм и мат.",
                    f"Ты смотришь видео с {name}. Напиши что ты думаешь об этом. Используй мат, чёрный юмор.",
                    f"Клип с {name} и другими стримерами. Напиши что происходит и кто кого переиграл.",
                    f"Ты смотришь на {accusative} в клипе и ржёшь. Напиши почему.",
                ]
            else:
                streamer_topics = [
                    "Клип со стримером. Что там происходит? Напиши короткий комментарий с критикой и матом.",
                    "Смотришь клип со стримером. Напиши что ты видишь и почему это смешно.",
                ]
            
            asian_topics = [
                "Ты смотришь фото из Азии. Что ты видишь? Почему это смешно или странно? Используй мат, сарказм.",
                "Фото из Азии. Что за херня там происходит? Напиши короткий комментарий.",
                "Ты смотришь видео из Азии. Что за дичь там творится? Опиши что происходит и почему это смешно.",
                "Азия, бля... Ты смотришь фото и не понимаешь что происходит. Напиши свой комментарий.",
                "Фото из Азии — там какая-то жесть. Твой комментарий к этому.",
                "Видео из Азии. Напиши что ты видишь и почему это забавно.",
            ]
            
            if attempt % 2 == 0:
                current_prompt = base_prompt + random.choice(streamer_topics if style == 'streamer' else asian_topics)
            else:
                # Альтернативный вариант с более конкретным указанием
                if style == 'streamer':
                    topic_prompt = random.choice(streamer_topics)
                else:
                    topic_prompt = random.choice(asian_topics)
                
                current_prompt = base_prompt + f"\n{topic_prompt}\n\n⚠️ Пиши строго в стиле примеров выше. Мат, сарказм, юмор. Коротко, 50-300 символов. 2 абзаца."
                logger.info(f"Пробую альтернативный промпт #{attempt}")
            
            system_prompt = get_system_prompt()
            
            url = DEEPSEEK_API_URL
            headers = {
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": DEEPSEEK_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": current_prompt}
                ],
                "temperature": 1.1,
                "max_tokens": 500,
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=60)
            
            if response.status_code == 400:
                error_text = response.text.lower()
                if "извините" in error_text or "не могу" in error_text or "не разрешено" in error_text:
                    logger.warning(f"Контент заблокирован, пробую другой промпт...")
                    continue
                else:
                    logger.error(f"Ошибка 400: {response.text[:200]}")
                    continue
            
            if response.status_code != 200:
                logger.error(f"DeepSeek ошибка {response.status_code}: {response.text[:200]}")
                time.sleep(1)
                continue
            
            result = response.json()
            if not result.get("choices") or len(result["choices"]) == 0:
                logger.warning("Нет choices в ответе")
                continue
            
            choice = result["choices"][0]
            generated_content = choice.get("message", {}).get("content", "")
            finish_reason = choice.get("finish_reason", "")
            
            if not generated_content or len(generated_content.strip()) < 20:
                logger.warning("Пустой или короткий ответ")
                continue
            
            if finish_reason == "length":
                continuation = request_continuation(generated_content)
                if continuation:
                    generated_content = generated_content.rstrip() + " " + continuation.strip()
            
            caption = generated_content.strip().strip('"').strip("'")
            
            if not caption:
                continue
            
            if caption.lower().startswith(("мы должны", "нужно", "я должен", "напиши", "вот", "давайте", "попробуем", "извините", "к сожалению", "я не могу", "не могу")):
                logger.warning("DeepSeek выдал рассуждение, пробуем другой промпт...")
                continue
            
            caption = clean_text(caption)
            
            # Проверяем наличие запрещённых фраз
            has_banned, banned_phrase = has_banned_phrases(caption)
            if has_banned:
                logger.warning(f"Найдена запрещённая фраза '{banned_phrase}', пробуем другой промпт...")
                continue
            
            # Проверяем количество абзацев
            paragraph_count = count_paragraphs(caption)
            
            if paragraph_count < 2:
                logger.warning(f"Пост содержит только {paragraph_count} абзац(ев), нужно минимум 2")
                continue
            
            logger.info(f"Пост содержит {paragraph_count} абзацев")
            
            # Проверяем длину поста (50-300 символов)
            if len(caption) < 50:
                logger.warning(f"Слишком короткий ({len(caption)} символов, нужно минимум 50)")
                continue
            
            if len(caption) > 300:
                caption = truncate_by_sentences(caption, 300)
                if len(caption) < 50:
                    logger.warning(f"После обрезания слишком короткий ({len(caption)} символов)")
                    continue
                logger.info(f"Пост обрезан до {len(caption)} символов (максимум 300)")
                
                # После обрезания проверяем заново
                paragraph_count = count_paragraphs(caption)
                if paragraph_count < 2:
                    logger.warning(f"После обрезания пост содержит только {paragraph_count} абзац(ев), нужно минимум 2")
                    continue
                
                has_banned, banned_phrase = has_banned_phrases(caption)
                if has_banned:
                    logger.warning(f"После обрезания найдена запрещённая фраза '{banned_phrase}', пробуем другой промпт...")
                    continue
            
            validated, error = validate_caption(caption, min_length=50, max_length=300)
            
            if not validated:
                logger.warning(f"Текст не прошёл проверку: {error}")
                continue
            
            approved, result = validate_post_with_deepseek(caption)
            
            if approved:
                logger.info(f"✅ Пост одобрен! (попытка {attempt+1}) Длина: {len(caption)} символов, абзацев: {paragraph_count}")
                add_to_last_posts(caption)
                return caption, streamer_key
            else:
                logger.warning(f"❌ Пост не прошёл проверку: {result}")
                continue
            
        except requests.exceptions.Timeout:
            logger.warning(f"Таймаут запроса (попытка {attempt+1})")
            continue
        except Exception as e:
            logger.error(f"Ошибка генерации (попытка {attempt+1}): {e}")
            continue
    
    logger.warning("⚠️ Все попытки генерации не удались")
    return "", streamer_key
