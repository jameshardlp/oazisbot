"""Планировщик для публикации мемов (скачивание и отправка с FFmpeg)."""
import asyncio
import logging
import random
import io
import time
import re
import os
import shutil
import subprocess
import tempfile
from typing import Optional

from telegram import InputFile
import settings
from config import CHANNEL_ID
from content import net
from content.meme_forwarder import get_random_meme_to_forward
from bot_modules.client import bot  # <-- ИСПРАВЛЕНО!

logger = logging.getLogger(__name__)

# Транскодирование не должно висеть вечно: битый контейнер заставляет ffmpeg
# читать поток бесконечно, а задача планировщика при этом не завершается
FFMPEG_TIMEOUT = 300

# Стратегия 4 переходит по вложенной ссылке t.me — без ограничения глубины
# страница, ссылающаяся на себя, зациклила бы разбор
MAX_MEDIA_URL_DEPTH = 2


def download_media(url: str) -> Optional[io.BytesIO]:
    """Скачивает медиа по ссылке в память."""
    if not url or not url.startswith('http'):
        logger.warning(f"⚠️ Невалидный URL: {url}")
        return None

    response = net.get(url, timeout=30, label="скачивание медиа")
    if response is None:
        return None

    if response.status_code != 200:
        logger.warning(f"⚠️ Скачивание медиа: HTTP {response.status_code}")
        return None

    content_type = response.headers.get('content-type', '')
    if any(t in content_type for t in ['image', 'video', 'gif']):
        return io.BytesIO(response.content)
    if len(response.content) > 10000:
        return io.BytesIO(response.content)

    logger.warning(
        f"⚠️ Скачивание медиа: ответ не похож на медиа "
        f"(content-type={content_type or '—'}, {len(response.content)} байт)"
    )
    return None


def convert_video_with_ffmpeg(input_data: bytes, output_format: str = "mp4") -> Optional[io.BytesIO]:
    """
    Конвертирует видео через FFmpeg в формат H.264 для Telegram.

    Временные файлы лежат в собственном каталоге и удаляются в finally.
    Раньше имена были фиксированными (temp_input_video в рабочей папке), поэтому
    два одновременных вызова затирали данные друг друга, а при отмене задачи
    мусор оставался на диске — очистка была размазана по except-блокам.
    """
    workdir = tempfile.mkdtemp(prefix="meme_ffmpeg_")
    temp_input = os.path.join(workdir, "input")
    temp_output = os.path.join(workdir, f"output.{output_format}")

    try:
        # Сохраняем входные данные во временный файл
        with open(temp_input, "wb") as f:
            f.write(input_data)

        # Проверяем размер входного файла
        input_size = os.path.getsize(temp_input)
        logger.info(f"📊 Размер входного видео: {input_size // 1024}KB")

        # Если файл слишком большой (более 45MB), пробуем сжать сильнее
        if input_size > 45 * 1024 * 1024:
            logger.info("🔄 Видео большое, применяю сильное сжатие...")
            crf_value = "28"
            preset = "slow"
        else:
            crf_value = "23"
            preset = "fast"

        # Команда FFmpeg: конвертирует в H.264 для Telegram.
        # -y обязателен: без него ffmpeg при уже существующем выходном файле
        # ждёт подтверждения со stdin и висит до таймаута.
        cmd = [
            "ffmpeg",
            "-y",
            "-i", temp_input,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-movflags", "+faststart",
            "-preset", preset,
            "-crf", crf_value,
            "-vf", "scale=1280:-2",
            temp_output
        ]

        logger.info(f"🔄 Запуск FFmpeg с параметрами: {' '.join(cmd)}")

        # Запускаем FFmpeg
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=FFMPEG_TIMEOUT,
        )

        if result.returncode != 0:
            logger.error(f"FFmpeg вернул код {result.returncode}: {(result.stderr or '')[-500:]}")
            return None

        # Проверяем, создался ли выходной файл
        if not os.path.exists(temp_output):
            logger.error("FFmpeg не создал выходной файл")
            return None

        # Читаем результат
        with open(temp_output, "rb") as f:
            result_data = f.read()

        logger.info(f"✅ Видео сконвертировано! Размер: {len(result_data) // 1024}KB")
        return io.BytesIO(result_data)

    except subprocess.TimeoutExpired:
        logger.error(f"FFmpeg не уложился в {FFMPEG_TIMEOUT}с, конвертация прервана")
        return None
    except FileNotFoundError:
        logger.error("FFmpeg не найден в PATH — видео отправится без конвертации")
        return None
    except Exception as e:
        logger.error(f"Ошибка FFmpeg: {e}")
        return None
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def get_direct_media_url(post_url: str, _depth: int = 0) -> Optional[str]:
    """Пытается получить прямую ссылку на медиа из поста.

    Стратегии перебираются по порядку, и в лог пишется, какая сработала:
    иначе сломанная вёрстка t.me выглядит как «в посте просто нет медиа».
    """
    try:
        response = net.get(post_url, label="страница поста t.me")
        if response is None:
            return None

        if response.status_code != 200:
            logger.warning(f"⚠️ Не удалось загрузить страницу поста: {response.status_code}")
            return None

        html = response.text

        # 1. Ищем прямые ссылки на файлы через теги <img> и <video>
        img_pattern = r'<img[^>]+src="(https?://[^"]+\.(?:jpg|jpeg|png|gif|webp))"'
        img_matches = re.findall(img_pattern, html, re.IGNORECASE)
        if img_matches:
            logger.info("🔎 Медиа найдено стратегией 1 (<img src>)")
            return img_matches[-1]

        video_pattern = r'<video[^>]+src="(https?://[^"]+\.(?:mp4|webm|mov))"'
        video_matches = re.findall(video_pattern, html, re.IGNORECASE)
        if video_matches:
            logger.info("🔎 Медиа найдено стратегией 1 (<video src>)")
            return video_matches[0]

        # 2. Ищем ссылки на файлы через data-bem
        bem_pattern = r'data-bem="({[^"]+})"'
        bem_matches = re.findall(bem_pattern, html)
        for bem_json in bem_matches:
            try:
                import json
                data = json.loads(bem_json)
                if 'photo' in data and 'src' in data['photo']:
                    src = data['photo']['src']
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/'):
                        src = 'https://t.me' + src
                    if '/preview/' in src:
                        src = src.replace('/preview/', '/file/')
                    logger.info("🔎 Медиа найдено стратегией 2 (data-bem)")
                    return src
            except Exception:
                pass

        # 3. Ищем любые ссылки с расширениями файлов
        file_pattern = r'https?://[^\s"\']+\.(?:jpg|jpeg|png|gif|mp4|webm|webp)'
        file_matches = re.findall(file_pattern, html, re.IGNORECASE)
        if file_matches:
            logger.info("🔎 Медиа найдено стратегией 3 (ссылка с расширением файла)")
            return file_matches[0]

        # 4. Ищем ссылки через Telegram file
        if _depth < MAX_MEDIA_URL_DEPTH:
            tg_file_pattern = r'https?://t\.me/[^/]+/\d+'
            tg_file_matches = re.findall(tg_file_pattern, html)
            for tg_url in tg_file_matches:
                if tg_url.rstrip('/') == post_url.rstrip('/'):
                    continue  # ссылка на себя же — переход ничего не даст
                logger.info(f"🔎 Стратегия 4: перехожу по вложенной ссылке {tg_url}")
                return get_direct_media_url(tg_url, _depth + 1)
        else:
            logger.warning(
                f"⚠️ Достигнут предел вложенности ссылок ({MAX_MEDIA_URL_DEPTH}), "
                f"дальше не идём: {post_url}"
            )

        net.log_layout_changed(
            "страница поста t.me", post_url,
            "ни одна из 4 стратегий не нашла ссылку на медиа",
        )
        return None

    except Exception as e:
        logger.error(f"Ошибка получения прямой ссылки: {e}")
        return None


async def send_meme_to_channel() -> bool:
    """Скачивает и отправляет мем в канал.

    Парсинг, скачивание и транскодирование — синхронные и тяжёлые, поэтому
    уходят в отдельный поток: иначе конвертация видео на минуты замораживала
    весь event loop и бот перестал бы отвечать на команды.
    """
    try:
        meme_data = await asyncio.to_thread(get_random_meme_to_forward)
        if not meme_data:
            logger.warning("⚠️ Нет доступных мемов")
            return False

        source_channel = meme_data.get('source_channel')
        message_id = meme_data.get('message_id')
        source_name = meme_data.get('source_name')

        if not source_channel or not message_id:
            return False

        logger.info(f"📥 Обрабатываю мем из {source_name} (ID: {message_id})")

        post_url = f"https://t.me/{source_channel.replace('@', '')}/{message_id}"
        logger.info(f"🔗 Загружаю страницу поста: {post_url}")

        direct_url = await asyncio.to_thread(get_direct_media_url, post_url)
        if not direct_url:
            logger.warning(f"⚠️ Не найдена прямая ссылка на медиа в посте {message_id}")
            return False

        logger.info(f"📥 Скачиваю медиа: {direct_url[:80]}...")

        media_data = await asyncio.to_thread(download_media, direct_url)
        if not media_data:
            logger.warning(f"⚠️ Не удалось скачать медиа")
            return False

        # Определяем тип по расширению
        url_lower = direct_url.lower()
        if any(ext in url_lower for ext in ['.jpg', '.jpeg', '.png', '.webp']):
            media_type = 'photo'
        elif any(ext in url_lower for ext in ['.mp4', '.mov', '.avi']):
            media_type = 'video'
        elif any(ext in url_lower for ext in ['.gif', '.webm']):
            media_type = 'animation'
        else:
            media_type = 'document'

        # Если это видео — конвертируем через FFmpeg
        if media_type == 'video':
            logger.info("🔄 Обнаружено видео, конвертирую через FFmpeg...")
            converted_data = await asyncio.to_thread(
                convert_video_with_ffmpeg, media_data.getvalue()
            )
            if converted_data:
                media_data = converted_data
                logger.info("✅ Видео успешно сконвертировано")
            else:
                logger.warning("⚠️ Не удалось сконвертировать видео, отправляю как есть")

        logger.info(f"📤 Отправляю {media_type} ({len(media_data.getvalue()) // 1024}KB)")

        # Отправляем с использованием InputFile
        if media_type == 'photo':
            await bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=InputFile(media_data, filename=f"meme_{int(time.time())}.jpg")
            )
        elif media_type == 'video':
            await bot.send_video(
                chat_id=CHANNEL_ID,
                video=InputFile(media_data, filename=f"meme_{int(time.time())}.mp4")
            )
        elif media_type == 'animation':
            await bot.send_animation(
                chat_id=CHANNEL_ID,
                animation=InputFile(media_data, filename=f"meme_{int(time.time())}.gif")
            )
        else:
            await bot.send_document(
                chat_id=CHANNEL_ID,
                document=InputFile(media_data, filename=f"meme_{int(time.time())}.bin")
            )

        logger.info(f"✅ Мем из {source_name} опубликован!")
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        return False


async def meme_scheduler():
    """Цикл планировщика мемов."""
    channels = settings.get_meme_channels()
    logger.info("=" * 60)
    logger.info("🎬 ПЛАНИРОВЩИК МЕМОВ ЗАПУЩЕН")
    logger.info(f"📡 Канал: {CHANNEL_ID}")
    logger.info(f"⏱️ Интервал: {settings.describe_interval()} (меняется командой /interval)")
    logger.info(f"📦 Источники: {', '.join(channels) if channels else 'не заданы — /sources add'}")
    logger.info("🔄 Режим: скачивание и отправка с FFmpeg и InputFile")
    logger.info("=" * 60)

    first_delay = random.randint(30, 60)
    logger.info(f"⏳ Первый мем через {first_delay} секунд...")
    await asyncio.sleep(first_delay)
    await send_meme_to_channel()

    count = 1

    while True:
        interval = settings.next_interval_seconds()
        logger.info(f"⏳ Следующий мем через {settings.format_interval(interval)}")

        # Не asyncio.sleep: /interval должен подействовать сразу, а не через часы
        if await settings.wait_for_next_post(interval):
            logger.info("♻️ Интервал изменён, отсчёт пошёл заново")
            continue

        success = await send_meme_to_channel()
        if success:
            count += 1
            logger.info(f"📊 Всего опубликовано мемов: {count}")
        else:
            logger.warning("⚠️ Публикация мема не удалась, пробую дальше...")
