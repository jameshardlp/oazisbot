"""Планировщик для публикации мемов (скачивание и отправка с FFmpeg)."""
import asyncio
import logging
import random
import io
import time
import re
import os
import subprocess
from datetime import datetime, timedelta
from typing import Optional

import requests
from telegram import InputFile
from config import CHANNEL_ID
from content.meme_forwarder import get_random_meme_to_forward
from telegram.client import bot

logger = logging.getLogger(__name__)

MIN_INTERVAL = 3600
MAX_INTERVAL = 10800


def download_media(url: str) -> Optional[io.BytesIO]:
    """Скачивает медиа по ссылке в память."""
    if not url or not url.startswith('http'):
        logger.warning(f"⚠️ Невалидный URL: {url}")
        return None

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, timeout=30, headers=headers)
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            if any(t in content_type for t in ['image', 'video', 'gif']):
                return io.BytesIO(response.content)
            if len(response.content) > 10000:
                return io.BytesIO(response.content)
        return None
    except Exception as e:
        logger.error(f"Ошибка скачивания: {e}")
        return None


def convert_video_with_ffmpeg(input_data: bytes, output_format: str = "mp4") -> Optional[io.BytesIO]:
    """
    Конвертирует видео через FFmpeg в формат H.264 для Telegram.
    """
    temp_input = "temp_input_video"
    temp_output = f"temp_output_video.{output_format}"
    
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
        
        # Команда FFmpeg: конвертирует в H.264 для Telegram
        cmd = [
            "ffmpeg",
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
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"FFmpeg ошибка: {result.stderr}")
            return None
        
        # Проверяем, создался ли выходной файл
        if not os.path.exists(temp_output):
            logger.error("FFmpeg не создал выходной файл")
            return None
        
        # Читаем результат
        with open(temp_output, "rb") as f:
            result_data = f.read()
        
        output_size = len(result_data)
        logger.info(f"✅ Видео сконвертировано! Размер: {output_size // 1024}KB")
        
        # Удаляем временные файлы
        os.remove(temp_input)
        os.remove(temp_output)
        
        return io.BytesIO(result_data)
        
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg ошибка: {e.stderr}")
        try:
            if os.path.exists(temp_input):
                os.remove(temp_input)
            if os.path.exists(temp_output):
                os.remove(temp_output)
        except:
            pass
        return None
    except Exception as e:
        logger.error(f"Ошибка FFmpeg: {e}")
        try:
            if os.path.exists(temp_input):
                os.remove(temp_input)
            if os.path.exists(temp_output):
                os.remove(temp_output)
        except:
            pass
        return None


def get_direct_media_url(post_url: str) -> Optional[str]:
    """Пытается получить прямую ссылку на медиа из поста."""
    try:
        response = requests.get(post_url, timeout=15, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        if response.status_code != 200:
            logger.warning(f"⚠️ Не удалось загрузить страницу поста: {response.status_code}")
            return None

        html = response.text

        # 1. Ищем прямые ссылки на файлы через теги <img> и <video>
        img_pattern = r'<img[^>]+src="(https?://[^"]+\.(?:jpg|jpeg|png|gif|webp))"'
        img_matches = re.findall(img_pattern, html, re.IGNORECASE)
        if img_matches:
            return img_matches[-1]

        video_pattern = r'<video[^>]+src="(https?://[^"]+\.(?:mp4|webm|mov))"'
        video_matches = re.findall(video_pattern, html, re.IGNORECASE)
        if video_matches:
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
                    return src
            except:
                pass

        # 3. Ищем любые ссылки с расширениями файлов
        file_pattern = r'https?://[^\s"\']+\.(?:jpg|jpeg|png|gif|mp4|webm|webp)'
        file_matches = re.findall(file_pattern, html, re.IGNORECASE)
        if file_matches:
            return file_matches[0]

        # 4. Ищем ссылки через Telegram file
        tg_file_pattern = r'https?://t\.me/[^/]+/\d+'
        tg_file_matches = re.findall(tg_file_pattern, html)
        if tg_file_matches:
            for tg_url in tg_file_matches:
                return get_direct_media_url(tg_url)

        logger.warning(f"⚠️ Не найдена прямая ссылка на медиа в посте {post_url}")
        return None

    except Exception as e:
        logger.error(f"Ошибка получения прямой ссылки: {e}")
        return None


async def send_meme_to_channel() -> bool:
    """Скачивает и отправляет мем в канал."""
    try:
        meme_data = get_random_meme_to_forward()
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

        direct_url = get_direct_media_url(post_url)
        if not direct_url:
            logger.warning(f"⚠️ Не найдена прямая ссылка на медиа в посте {message_id}")
            return False

        logger.info(f"📥 Скачиваю медиа: {direct_url[:80]}...")

        media_data = download_media(direct_url)
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
            converted_data = convert_video_with_ffmpeg(media_data.getvalue())
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
    logger.info("=" * 60)
    logger.info("🎬 ПЛАНИРОВЩИК МЕМОВ ЗАПУЩЕН")
    logger.info(f"📡 Канал: {CHANNEL_ID}")
    logger.info(f"⏱️ Интервал: 1-3 часа")
    logger.info("📦 Источники: videos_dolboyoba, shitcollection, postleftism, noviop")
    logger.info("🔄 Режим: скачивание и отправка с FFmpeg и InputFile")
    logger.info("=" * 60)

    first_delay = random.randint(30, 60)
    logger.info(f"⏳ Первый мем через {first_delay} секунд...")
    await asyncio.sleep(first_delay)
    await send_meme_to_channel()

    count = 1

    while True:
        next_interval = random.randint(MIN_INTERVAL, MAX_INTERVAL)
        hours = next_interval // 3600
        minutes = (next_interval % 3600) // 60

        logger.info(f"⏳ Следующий мем через {hours}ч {minutes}м")
        await asyncio.sleep(next_interval)

        success = await send_meme_to_channel()
        if success:
            count += 1
            logger.info(f"📊 Всего опубликовано мемов: {count}")
        else:
            logger.warning("⚠️ Публикация мема не удалась, пробую дальше...")
