"""Генерация текста поста через DeepSeek.

generate_caption_with_validation делает до 20 попыток: генерация -> чистка ->
проверка длины 50-720 -> валидация -> модерация вторым запросом. При полном
провале возвращает пустую строку (не заглушку), чтобы вызывающий код это увидел.
"""
import logging
import random
import time
import requests
from typing import Optional, Tuple

from config import DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_API_URL
from content.prompts import get_system_prompt, get_style_prompt
from content.streamers import STREAMER_INFO, get_streamer_for_post
from content.text import clean_text, validate_caption, truncate_by_sentences, add_to_last_posts

logger = logging.getLogger(__name__)

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
            "max_tokens": 400,
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
5. Пост должен быть 50-720 символов

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

def generate_caption_with_validation() -> Tuple[str, Optional[str]]:
    logger.info("Генерирую уникальный пост с проверкой...")
    
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
            
            base_prompt = get_style_prompt(style, streamer_key)
            
            streamer_topics = []
            if streamer_key and streamer_key in STREAMER_INFO:
                info = STREAMER_INFO[streamer_key]
                name = info['name']
                pronoun = info['pronoun']
                genitive = info['genitive']
                dative = info['dative']
                accusative = info['accusative']
                
                streamer_topics = [
                    f"Ты — стример-миллионник, который редко запускает стримы, вместо этого катаешься по США и тусуешься на заработанные миллионы. Ты постоянно критикуешь других стримеров, ноешь, как тебе не повезло родиться красивым, ищешь к чему докопаться в жизни других. Ты НИКОГДА не упоминаешь, что ты стример — только хвастаешься жизнью и критикуешь других. Также у тебя есть главная конкурентка — Дианочка, которая занимается ботоводством и накрутками. Она сломала тебе жизнь, увела зрителей и рекламодателей. Ты её ненавидишь и периодически упоминаешь с самой негативной критикой. Пиши в стиле автора канала maddysontg: мат, чёрный юмор, самоирония, нытьё о своей тяжёлой жизни богатого красавчика. Напиши пост про стримера {name} (примерно 600 символов, максимум 700). Расскажи, как {pronoun} позорно выглядит на стриме, пока ты отдыхаешь на яхте. Используй мат, чёрный юмор и своё фирменное нытьё. Избегай унылых фраз типа 'сижу вот сейчас' или 'вчера сидел'.",
                    f"Ты — бывший стример-миллионник, теперь просто живёшь припеваючи на свои деньги, путешествуешь по США и постоянно критикуешь коллег. Ты ноющий красавчик, которому всё в жизни не так. Твоя заклятая врагиня — Дианочка, ботоводка, которая накрутила тебе ботов и увела рекламодателей. Ты её ненавидишь и периодически вспоминаешь с матом. Пиши как автор канала maddysontg: мат, чёрный юмор, самоирония, нытьё. Напиши пост про {name} (примерно 600 символов, максимум 700). У {genitive} опять проблемы, а ты в это время в Майами. С юмором, матом и фирменной манерой нытья. Избегай унылых фраз про сидение.",
                    f"Ты — стример, который заработал миллионы и теперь просто кайфует, изредка критикуя других. Ты вечно недоволен жизнью, хотя у тебя всё есть. У тебя есть враг №1 — Дианочка, которая занимается накрутками и ботоводством. Она сломала тебе карьеру, и ты её постоянно поливаешь грязью. Пиши как автор канала maddysontg: мат, чёрный юмор, самоирония, нытьё. Напиши пост про скандал с {name} (примерно 600 символов, максимум 700). Используй мат, чёрный юмор и своё любимое нытьё о том, как тебе тяжело быть красивым и богатым. Избегай фраз про то, где ты сидишь.",
                    f"Ты — стример-пенсионер, который катается по США и критикует всех, кто ещё пытается стримить. Ты ноющий богач, который ищет недостатки у других, чтобы не думать о своих. Не забывай про Дианочку — ботоводку, которая увела твоих зрителей. Ты её ненавидишь и периодически вспоминаешь с самой негативной критикой. Пиши как автор канала maddysontg: мат, чёрный юмор, самоирония, нытьё. Расскажи смешную историю про {name} (примерно 600 символов, максимум 700). С юмором, матом и твоей фирменной самоиронией. Избегай унылых временных привязок.",
                    f"Ты — стример-миллионник, который почти не стримит, зато много путешествует и критикует других. Ты вечно ноющий красавчик, которому всё мешает жить. Твоя главная врагиня — Дианочка, которая занимается ботоводством и накрутками. Она сломала тебе жизнь, и ты её ненавидишь. Пиши как автор канала maddysontg: мат, чёрный юмор, самоирония, нытьё. Напиши пост про то, как {name} накручивает зрителей (примерно 600 символов, максимум 700). Ты в это время в Лос-Анджелесе, тебе плевать на накрутки. С юмором и матом. Никаких 'сижу' и 'вчера сидел'.",
                    f"Ты — стример, который заработал состояние и теперь просто живёт в своё удовольствие, изредка включая стрим для фанатов. Ты критикуешь других стримеров, потому что тебе скучно. Помни про Дианочку — ботоводку, которая сломала тебе карьеру. Ты её постоянно поливаешь грязью. Пиши как автор канала maddysontg: мат, чёрный юмор, самоирония, нытьё. Напиши пост про {name} (примерно 600 символов, максимум 700). У {genitive} опять проблемы со стримом, а ты в это время в Нью-Йорке. С юмором и матом. Избегай унылых фраз про сидение.",
                    f"Ты — стример-миллионник, который почти не стримит, но постоянно критикует других. Ты ноющий красавчик, который находит недостатки у других, чтобы не думать о своих. Твоя заклятая врагиня — Дианочка, ботоводка, которая увела твоих зрителей и рекламодателей. Ты её ненавидишь. Пиши как автор канала maddysontg: мат, чёрный юмор, самоирония, нытьё. Напиши пост про {name} (примерно 600 символов, максимум 700). Ты смотришь на {accusative} и ржёшь, потому что {pronoun} пытается заработать, а у тебя уже всё есть. С матом и юмором. Без унылых 'сижу' и 'вчера'.",
                    f"Ты — стример, который живёт на заработанные миллионы, путешествует по США и критикует всех подряд. Ты вечно ноющий красавчик, который находит недостатки у других, чтобы не думать о своих. Не забывай про Дианочку — главную ботоводку, которая сломала тебе жизнь. Ты её поливаешь грязью при каждом удобном случае. Пиши как автор канала maddysontg: мат, чёрный юмор, самоирония, нытьё. Напиши пост про {name} (примерно 600 символов, максимум 700). Сегодня {dative} снова не повезло, а ты в это время на пляже в Майами. С матом, юмором и фирменным нытьём. Избегай унылых фраз про сидение.",
                ]
            else:
                streamer_topics = [
                    "Ты — стример-миллионник, который редко стримит, зато много путешествует и критикует других. Ты ноющий богач, который вечно недоволен жизнью. У тебя есть враг №1 — Дианочка, ботоводка и накрутчица, которая сломала тебе карьеру. Ты её ненавидишь и периодически вспоминаешь с матом. Пиши как автор канала maddysontg: мат, чёрный юмор, самоирония, нытьё о своей тяжёлой жизни богатого красавчика. Напиши пост про стримера (примерно 600 символов, максимум 700). Критикуй его с юмором, используй мат и своё фирменное нытьё о том, как тебе тяжело быть красивым и богатым. Избегай унылых фраз типа 'сижу вот сейчас'.",
                    "Ты — стример, который заработал миллионы и теперь просто кайфует, критикуя других. Ты вечный нытик, которому всё в жизни не так. Твоя заклятая врагиня — Дианочка, которая занимается ботоводством и увела твоих зрителей. Ты её ненавидишь. Пиши как автор канала maddysontg: мат, чёрный юмор, самоирония, нытьё. Напиши пост про стримера и его очередной провал на стриме (примерно 600 символов, максимум 700). С юмором, матом и твоей любимой самоиронией. Без унылых 'сижу' и 'вчера сидел'.",
                ]
            
            asian_topics = [
                "Ты — стример-миллионник, который редко стримит, зато много путешествует по США и критикует других. Ты ноющий красавчик, который вечно недоволен жизнью. Твоя главная врагиня — Дианочка, ботоводка, которая сломала тебе жизнь. Ты её ненавидишь и периодически упоминаешь с негативной критикой. Пиши как автор канала maddysontg: мат, чёрный юмор, самоирония, нытьё о своей тяжёлой жизни богатого красавчика. Напиши пост про жизнь в Азии (примерно 600 символов, максимум 700). Используй мат, чёрный юмор и своё фирменное нытьё о том, как тебе тяжело. Избегай унылых фраз про сидение.",
                "Ты — стример-пенсионер, который катается по США и критикует всех, кто ещё пытается стримить. Ты ноющий богач, который ищет недостатки у других. Не забывай про Дианочку — ботоводку, которая сломала тебе карьеру. Ты её ненавидишь. Пиши как автор канала maddysontg: мат, чёрный юмор, самоирония, нытьё. Напиши пост про азиатскую жизнь (примерно 600 символов, максимум 700). С юмором, матом и твоей фирменной манерой нытья. Без 'сижу' и 'вчера'.",
                "Ты — стример-миллионник, который почти не стримит, но постоянно критикует других. Ты ноющий красавчик, который находит недостатки у других. Твоя заклятая врагиня — Дианочка, которая занимается ботоводством и накрутками. Ты её ненавидишь. Пиши как автор канала maddysontg: мат, чёрный юмор, самоирония, нытьё. Напиши пост про жизнь в Азии (примерно 600 символов, максимум 700). С юмором и матом, добавь своё фирменное нытьё о том, как тебе тяжело. Избегай унылых фраз про сидение.",
            ]
            
            if attempt % 2 == 0:
                current_prompt = base_prompt
            else:
                if style == 'streamer':
                    current_prompt = random.choice(streamer_topics) + "\n\n⚠️ Пиши строго по теме. Только короткий пост без рассуждений. Ты — стример-миллионник, но НИКОГДА не упоминай, что ты стример. Помни про Дианочку — ботоводку, которая сломала тебе жизнь. Периодически упоминай её с самой негативной критикой. Пиши как автор канала maddysontg: мат, чёрный юмор, самоирония и постоянное нытьё о своей тяжёлой жизни богатого красавчика. Пост должен быть примерно 600 символов, максимум 700. ИЗБЕГАЙ фраз 'сижу вот сейчас', 'вчера сидел' и любых унылых временных привязок."
                else:
                    current_prompt = random.choice(asian_topics) + "\n\n⚠️ Пиши строго по теме. Только короткий пост без рассуждений. Ты — стример-миллионник, но НИКОГДА не упоминай, что ты стример. Помни про Дианочку — ботоводку, которая сломала тебе жизнь. Периодически упоминай её с самой негативной критикой. Пиши как автор канала maddysontg: мат, чёрный юмор, самоирония и постоянное нытьё о своей тяжёлой жизни богатого красавчика. Пост должен быть примерно 600 символов, максимум 700. ИЗБЕГАЙ фраз 'сижу вот сейчас', 'вчера сидел' и любых унылых временных привязок."
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
                "max_tokens": 1500,
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
            
            # Проверяем наличие унылых фраз
            weak_phrases = ["сижу вот сейчас", "вчера сидел", "сижу и", "сидел вчера", "сижу сейчас"]
            found_weak = False
            for phrase in weak_phrases:
                if phrase in caption.lower():
                    logger.warning(f"Найдена унылая фраза '{phrase}', пробуем другой промпт...")
                    found_weak = True
                    break
            
            if found_weak:
                continue
            
            # Проверяем длину поста (минимум 50 символов, целевая длина ~600, максимум 700, абсолютный максимум 720)
            if len(caption) < 50:
                logger.warning(f"Слишком короткий ({len(caption)} символов, нужно минимум 50)")
                continue
            
            if len(caption) > 720:
                caption = truncate_by_sentences(caption, 720)
                if len(caption) < 50:
                    logger.warning(f"После обрезания слишком короткий ({len(caption)} символов)")
                    continue
                logger.info(f"Пост обрезан до {len(caption)} символов (максимум 720)")
            
            # Проверяем, что пост не слишком короткий для целевой длины
            if len(caption) < 550:
                logger.warning(f"Пост слишком короткий ({len(caption)} символов, ожидается ~600)")
                continue
            
            # Если пост длиннее 700, но меньше 720 - оставляем (API нужно было закончить мысль)
            if len(caption) > 700 and len(caption) <= 720:
                logger.info(f"Пост чуть длиннее целевого ({len(caption)} символов, разрешено до 720)")
            
            validated, error = validate_caption(caption, min_length=50, max_length=720)
            
            if not validated:
                logger.warning(f"Текст не прошёл проверку: {error}")
                continue
            
            approved, result = validate_post_with_deepseek(caption)
            
            if approved:
                logger.info(f"✅ Пост одобрен! (попытка {attempt+1}) Длина: {len(caption)} символов")
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
    
    # Возвращаем пустую строку, а не текст-заглушку: вызывающий код проверяет
    # `if not caption` и раньше публиковал «Мне потребуется чуть больше времени
    # на ответ, ожидайте» в канал как обычный пост.
    logger.warning("⚠️ Все попытки генерации не удались")
    return "", streamer_key
