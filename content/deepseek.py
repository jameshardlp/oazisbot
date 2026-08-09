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
from typing import Optional, Tuple, List

from config import DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_API_URL
from content.prompts import get_system_prompt, get_style_prompt
from content.streamers import STREAMER_INFO, get_streamer_for_post
from content.text import clean_text, validate_caption, truncate_by_sentences, add_to_last_posts
from content.channel_parser import get_posts_from_channel_web, get_default_style_examples

logger = logging.getLogger(__name__)

# Глобальный кэш для контекста стиля
_style_context_cache = ""
_raw_posts_cache = []
_cache_time = 0
CACHE_TTL = 3600  # Обновлять раз в час

# ===== ПЕРСОНАЛЬНЫЕ ХАРАКТЕРИСТИКИ СТРИМЕРОВ =====
STREAMER_PERSONALITIES = {
    "bratishkinoff": {
        "nicknames": ["Братишкин", "братишка"],
        "traits": "тупой, полный идиот, орёт как потерпевший",
        "style": "критический, уничижительный",
        "pronoun": "он",
        "possessive": "его",
        "examples": [
            "Братишкин опять показывает свой IQ комнатной температуры.",
            "Этот идиот даже не понимает, что делает.",
            "Братишкин — живое доказательство теории Дарвина.",
            "Братишкин опять ловит хайп на ровном месте, орёт как потерпевший."
        ]
    },
    "sasavot": {
        "nicknames": ["Сасайрот", "Сасавот", "саса"],
        "traits": "бездарный, крутит ботов",
        "style": "насмешливый, обвинительный",
        "pronoun": "он",
        "possessive": "его",
        "examples": [
            "Сасайрот опять накрутил ботов, а сам даже говорить не умеет.",
            "Бездарность Сасайрота зашкаливает, одни боты его и спасают.",
            "Сасайрот — король ботоводов, а не стример."
        ]
    },
    "alina_rin": {
        "nicknames": ["Алина Рин", "Алиночка", "Рин"],
        "traits": "милая, няшная, но злая",
        "style": "двойственный — сначала мило, потом жёстко",
        "pronoun": "она",
        "possessive": "её",
        "examples": [
            "Алина Рин такая няшка, но если её разозлить — берегись!",
            "Милая Алиночка, которая может уничтожить любого одним словом.",
            "Рин — милаха с характером тигрицы."
        ]
    },
    "praden": {
        "nicknames": ["енот", "Праден", "прадик"],
        "traits": "душный, унылый, как енот",
        "style": "унылый, занудный",
        "pronoun": "он",
        "possessive": "его",
        "examples": [
            "Праден опять душный, как старый енот в норе.",
            "Енот Праден уныло вещает, хочется спать.",
            "Праден — король уныния и душности."
        ]
    },
    "buster": {
        "nicknames": ["Бубстер", "Бустер", "буб"],
        "traits": "лишний вес, карьера скоро закончится",
        "style": "издевательский, предсказывающий крах",
        "pronoun": "он",
        "possessive": "его",
        "examples": [
            "Бубстеру пора худеть, а не стримить.",
            "Карьера Бубстера катится в жопу, если не уйдёт от Дианочки.",
            "Бубстер — ходячий мем с лишним весом."
        ]
    },
    "arrowwoods": {
        "nicknames": ["дядя Добро", "Аравудус", "Ара"],
        "traits": "неудачи в Мэхамене",
        "style": "добродушно-насмешливый",
        "pronoun": "он",
        "possessive": "его",
        "examples": [
            "Дядя Добро опять слил в Мэхамене.",
            "Аравудус снова проиграл в Мэхамены.",
            "Мэхамены снова уничтожили дядю Добро."
        ]
    },
    "nenormova": {
        "nicknames": ["дворняга", "Галя", "Ульяна", "Ненормова"],
        "traits": "красивая, милая, лучшая стримерша на всём рутвиче",
        "style": "восторженный, восхищённый",
        "pronoun": "она",
        "possessive": "её",
        "gender": "female",
        "examples": [
            "Наша дворняга Галя снова лучшая!",
            "Ульяна Ненормова — королева рутвича, милаха и красотка.",
            "Ненормова — лучшая стримерша, просто богиня."
        ]
    }
}

def get_streamer_personality(streamer_key: str) -> dict:
    """Возвращает персонализацию для стримера."""
    return STREAMER_PERSONALITIES.get(streamer_key, {})

def fetch_and_cache_posts(limit: int = 10, force_refresh: bool = False) -> List[str]:
    """
    Получает посты из канала и кэширует их для обучения.
    """
    global _raw_posts_cache, _cache_time
    
    current_time = time.time()
    
    if not force_refresh and _raw_posts_cache and (current_time - _cache_time) < CACHE_TTL:
        logger.info(f"📦 Использую кэшированные посты ({len(_raw_posts_cache)} постов)")
        return _raw_posts_cache
    
    try:
        posts = get_posts_from_channel_web(limit=limit)
        
        if posts:
            _raw_posts_cache = posts
            _cache_time = current_time
            logger.info(f"✅ Загружено {len(posts)} постов из канала для обучения")
            return posts
        else:
            logger.warning("⚠️ Не удалось загрузить посты, использую заглушку")
            posts = get_default_style_examples()
            _raw_posts_cache = posts
            _cache_time = current_time
            return posts
            
    except Exception as e:
        logger.error(f"❌ Ошибка при получении постов: {e}")
        posts = get_default_style_examples()
        _raw_posts_cache = posts
        _cache_time = current_time
        return posts

def get_style_context(limit: int = 3, force_refresh: bool = False) -> str:
    """
    Формирует контекст стиля из постов канала maddysontg.
    Использует реальные посты для обучения правильным формулировкам.
    """
    global _style_context_cache
    
    # Получаем свежие посты
    posts = fetch_and_cache_posts(limit=10, force_refresh=force_refresh)
    
    if not posts:
        return "Используй мат, чёрный юмор, сарказм и самоиронию. Пиши коротко и ёмко."
    
    # Берём первые limit постов для примера
    sample_posts = posts[:limit]
    
    # Формируем контекст с примерами и акцентом на грамматику
    context = """⚠️ ЭТО ОЧЕНЬ ВАЖНО: Ниже приведены РЕАЛЬНЫЕ посты из канала. 
Ты должен учиться ПРАВИЛЬНЫМ формулировкам именно из них. 
Обрати внимание на грамматику, падежи, местоимения — в этих постах всё правильно.

Вот примеры постов в стиле, котором нужно писать:

"""
    for i, post in enumerate(sample_posts, 1):
        context += f"--- ПРИМЕР {i} (оригинал из канала) ---\n{post}\n\n"
    
    context += """
⚠️ ПРАВИЛА НА ОСНОВЕ ЭТИХ ПРИМЕРОВ:
1. Используй ТОЧНО такие же грамматические конструкции
2. Правильно используй падежи и местоимения (как в примерах)
3. Не придумывай свои обороты — копируй стиль из примеров
4. Если в примерах нет какой-то фразы — значит её не существует в этом стиле
5. НЕЛЬЗЯ писать "глаза б на меня не глядели" — в примерах такого нет
6. Пиши коротко, ёмко, с матом и юмором, как в примерах

Пиши в ТОЧНО таком же стиле, как в примерах выше. Используй те же обороты, ту же лексику, ту же манеру изложения.
"""
    
    _style_context_cache = context
    return context

def get_personality_prompt(streamer_key: str, streamer_name: str) -> str:
    """
    Возвращает персонализированный промпт для конкретного стримера.
    Теперь с акцентом на обучение из примеров.
    """
    personality = get_streamer_personality(streamer_key)
    
    if not personality:
        return f"Напиши комментарий к клипу со стримером {streamer_name}. Используй стиль из примеров выше."
    
    nicknames = personality.get("nicknames", [streamer_name])
    traits = personality.get("traits", "")
    pronoun = personality.get("pronoun", "он")
    possessive = personality.get("possessive", "его")
    examples = personality.get("examples", [])
    
    main_nick = random.choice(nicknames)
    
    # Формируем промпт с явной ссылкой на примеры из канала
    base = f"""Напиши комментарий к клипу со стримером {streamer_name}.

⚠️ ИСПОЛЬЗУЙ СТИЛЬ ИЗ ПРИМЕРОВ ВЫШЕ:
- Те же грамматические конструкции
- Те же обороты речи
- Те же падежи и местоимения
- Те же выражения и мемы

О стримере:
- Называй его/её: {main_nick}
- Характеристика: {traits}
- Местоимения: {pronoun}, {possessive}

Примеры того, как писать про этого стримера:
"""
    for ex in examples[:2]:
        base += f"- {ex}\n"
    
    base += f"""
⚠️ НЕ ПРИДУМЫВАЙ СВОИ ОБОРОТЫ — используй только те, что есть в примерах из канала!
Если в примерах нет какой-то фразы — значит её не должно быть в твоём посте.
"""
    
    return base

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
9. Пост должен использовать правильные грамматические конструкции (без ошибок типа "глаза б на меня не глядели")
10. Пост должен соответствовать стилю примеров из канала

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
        
        # Неправильные грамматические конструкции
        (r'глаза\s+б\s+на\s+меня\s+не\s+глядели', 'глаза б на меня не глядели (грамматическая ошибка)'),
        (r'глаза\s+на\s+меня\s+не\s+гляд', 'глаза на меня не гляд (грамматическая ошибка)'),
    ]
    
    text_lower = text.lower()
    for pattern, phrase in banned_phrases:
        if re.search(pattern, text_lower):
            return True, phrase
    
    return False, ""

def generate_caption_with_validation() -> Tuple[str, Optional[str]]:
    """
    Генерирует пост с проверкой.
    Для чтения стиля из канала используется веб-парсер (без API ключей).
    """
    logger.info("Генерирую уникальный пост с проверкой...")
    
    # Получаем стиль из канала maddysontg через веб-парсер
    style_context = get_style_context(limit=5)  # Берём 5 примеров для лучшего обучения
    
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

⚠️ ГЛАВНОЕ ПРАВИЛО:
НЕ ПРИДУМЫВАЙ СВОИ ФРАЗЫ! 
Используй ТОЛЬКО те формулировки, которые есть в примерах из канала выше.
Если в примерах нет "глаза б на меня не глядели" — значит ТАК НЕЛЬЗЯ ПИСАТЬ.

СТРОГО ЗАПРЕЩЕНО использовать фразы: 'сижу', 'вчера сидел', 'пиво пью', 'листаю стрим', 'я думаю', 'мне кажется'.
ОБЯЗАТЕЛЬНО раздели пост на 2 абзаца.
Длина: 50-300 символов.
"""
            
            # Получаем персонализированный промпт для стримера
            personality_prompt = ""
            if style == 'streamer' and streamer_key:
                personality_prompt = get_personality_prompt(streamer_key, streamer_display)
            
            streamer_topics = []
            if streamer_key and streamer_key in STREAMER_INFO:
                info = STREAMER_INFO[streamer_key]
                name = info['name']
                pronoun = info['pronoun']
                genitive = info['genitive']
                dative = info['dative']
                accusative = info['accusative']
                
                # Базовые темы (общие)
                base_streamer_topics = [
                    f"Клип с {name}. Что там происходит? {pronoun} снова позорится? Или Дианочка накрутила {dative} ботов? Напиши короткий комментарий, используя стиль из примеров.",
                    f"Ты смотришь клип с {name}. В клипе видно как {pronoun} что-то делает. Опиши это и дай оценку. Критикуй, смейся, используй мат, как в примерах.",
                    f"Клип с участием {name}. Что {pronoun} сделал не так? Или наоборот — красавчик? Используй сарказм и мат, как в примерах из канала.",
                    f"Ты смотришь видео с {name}. Напиши что ты думаешь об этом. Используй мат, чёрный юмор, как в примерах.",
                    f"Клип с {name} и другими стримерами. Напиши что происходит и кто кого переиграл, в стиле примеров.",
                    f"Ты смотришь на {accusative} в клипе и ржёшь. Напиши почему, используя формулировки из примеров.",
                ]
                
                if personality_prompt:
                    personalized_topics = [
                        f"{personality_prompt} Используй мат, сарказм, как в примерах.",
                        f"{personality_prompt} Будь максимально жёстким/восторженным, как в примерах.",
                        f"{personality_prompt} Пиши коротко, 50-300 символов, в стиле примеров.",
                    ]
                    streamer_topics = personalized_topics + base_streamer_topics
                else:
                    streamer_topics = base_streamer_topics
            else:
                streamer_topics = [
                    "Клип со стримером. Напиши короткий комментарий с критикой и матом, как в примерах из канала.",
                    "Смотришь клип со стримером. Напиши что ты видишь и почему это смешно, в стиле примеров.",
                ]
            
            asian_topics = [
                "Ты смотришь фото из Азии. Что ты видишь? Почему это смешно или странно? Используй мат, сарказм, как в примерах.",
                "Фото из Азии. Что за херня там происходит? Напиши короткий комментарий в стиле примеров.",
                "Ты смотришь видео из Азии. Что за дичь там творится? Опиши что происходит и почему это смешно, как в примерах.",
                "Азия, бля... Ты смотришь фото и не понимаешь что происходит. Напиши свой комментарий в стиле примеров.",
                "Фото из Азии — там какая-то жесть. Твой комментарий к этому, как в примерах.",
                "Видео из Азии. Напиши что ты видишь и почему это забавно, в стиле примеров.",
            ]
            
            if attempt % 2 == 0:
                if style == 'streamer' and personality_prompt:
                    current_prompt = base_prompt + random.choice(streamer_topics[:3])
                else:
                    current_prompt = base_prompt + random.choice(streamer_topics if style == 'streamer' else asian_topics)
            else:
                if style == 'streamer':
                    topic_prompt = random.choice(streamer_topics)
                else:
                    topic_prompt = random.choice(asian_topics)
                
                current_prompt = base_prompt + f"\n{topic_prompt}\n\n⚠️ ЕЩЁ РАЗ: НЕ ПРИДУМЫВАЙ СВОИ ФРАЗЫ! Используй ТОЛЬКО формулировки из примеров выше. Мат, сарказм, юмор. Коротко, 50-300 символов. 2 абзаца."
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
