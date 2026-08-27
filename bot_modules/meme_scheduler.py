"""Планировщик публикации мемов: скачивание и отправка в канал.

Ссылки на медиа даёт content/meme_forwarder — он разбирает ту же страницу
t.me/s/<канал>, по которой ищет посты. Раньше поиском ссылок занимался этот
модуль (get_direct_media_url, четыре регулярки по странице одиночного поста), но
на t.me/<канал>/<id> нет ни mp4, ни всех фото альбома — только og:image-превью.
Поэтому видео не публиковались вовсе, а из альбома уходило одно фото.

Из поста-альбома публикуется РОВНО ОДИН элемент, а не media_group. Причина не в
предпочтениях: send_media_group с готовыми InputFile формировал битый запрос —
python-telegram-bot возвращает уже созданный InputFile из parse_file_input как
есть, attach://-имени у него нет, и в multipart вместо JSON-описания альбома
уходило поле media с байтами одного файла. Telegram такие посты отклонял, то
есть любой пост с двумя и более медиа не публиковался никогда.

FFmpeg теперь резерв, а не обязательный этап: t.me отдаёт видео уже в формате
Telegram (H.264/AAC, faststart), и перекодирование каждого файла было минутами
работы и лишней точкой отказа. Перекодируем только то, что Telegram не принял
или что не пролезает по размеру.

Один и тот же мем в канал не уходит дважды: что уже публиковалось, помнит
content/posted_store — по посту, по файлу и по sha256 самих байтов. Последнее
ловит и перезалив того же видео в другом канале-источнике, где и ссылка, и id
поста другие.
"""
import asyncio
import io
import logging
import os
import random
import shutil
import subprocess
import tempfile
import time
from typing import Dict, List, Optional, Tuple

import requests
from telegram import InputFile
from telegram.error import RetryAfter, TelegramError, TimedOut

import settings
from config import CHANNEL_ID
from content import net, posted_store
from content.meme_forwarder import fetch_post_media, get_meme_candidates
from bot_modules.client import bot

logger = logging.getLogger(__name__)

# Транскодирование не должно висеть вечно: битый контейнер заставляет ffmpeg
# читать поток бесконечно, а задача планировщика при этом не завершается
FFMPEG_TIMEOUT = 300

# Сколько постов пробуем за одну публикацию. У отдельного поста медиа может не
# скачаться (t.me не ответил, токен в ссылке просрочен), и раньше такая осечка
# означала полный провал: /postnow «работал через раз», а планировщик замолкал
# до следующего интервала.
MAX_CANDIDATES = 5

# Сколько элементов одного поста пробуем скачать, прежде чем признать пост
# неудачным. В альбоме это бесплатный резерв: не скачалось первое фото — берём
# следующее, пост всё равно уйдёт.
MAX_MEDIA_TRIES = 3

# Bot API не принимает файлы больше 50 МБ
TELEGRAM_UPLOAD_LIMIT = 50 * 1024 * 1024

# Пауза после неудачной публикации. Раньше цикл ждал полный интервал (до трёх
# часов) — со стороны это выглядело как «мемы не постятся вообще».
RETRY_AFTER_FAILURE = 5 * 60

# Таймауты на отправку медиа. Дефолтные 20 с на чтение ответа видео не хватает:
# Telegram после аплоада обрабатывает файл у себя, и отказ по таймауту выглядел
# как «Telegram не принимает видео».
SEND_READ_TIMEOUT = 180
SEND_WRITE_TIMEOUT = 300


def download_media(
    url: str, session: Optional[requests.Session] = None
) -> Optional[io.BytesIO]:
    """Скачивает медиа по ссылке в память."""
    if not url or not url.startswith('http'):
        logger.warning(f"⚠️ Невалидный URL: {url}")
        return None

    response = net.get(url, timeout=30, label="скачивание медиа", session=session)
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
        # min(1280,iw): только уменьшаем. Жёсткое scale=1280 растягивало
        # вертикальные мемы вверх по разрешению, и «сжатие» давало файл в
        # несколько раз тяжелее исходного.
        cmd = [
            "ffmpeg",
            "-y",
            "-i", temp_input,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-movflags", "+faststart",
            "-preset", preset,
            "-crf", crf_value,
            "-vf", "scale=w='min(1280,iw)':h=-2",
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
        logger.error("FFmpeg не найден в PATH — перекодировать видео нечем")
        return None
    except Exception as e:
        logger.error(f"Ошибка FFmpeg: {e}")
        return None
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def pick_candidates(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Медиа поста в порядке предпочтения: сначала видео, затем фото.

    Публикуется только первый скачавшийся элемент. Видео вперёд, потому что в
    смешанном альбоме оно и есть содержание поста, а фото рядом — кадр или
    подпись.

    Файлы, которые уже уходили в канал, отбрасываются здесь же: проверка по
    ссылке бесплатная, а для видео путь в url телеско.pe — это сам файл, так что
    повтор виден до скачивания.
    """
    fresh = [item for item in items if not posted_store.is_file_posted(item.get('url', ''))]
    if len(fresh) != len(items):
        logger.info(f"🧠 Пропускаю {len(items) - len(fresh)} медиа: такие файлы уже публиковались")

    videos = [item for item in fresh if item.get('type') == 'video']
    photos = [item for item in fresh if item.get('type') != 'video']
    return videos + photos


def download_first(items: List[Dict[str, str]]) -> Optional[Dict]:
    """Скачивает первый годный элемент поста: {'type', 'url', 'data'} или None.

    Размер здесь не проверяем: слишком тяжёлое видео умеет спасти ffmpeg,
    решение принимает _publish.

    Байты сверяем с историей публикаций: тот же файл мог быть перезалит в другой
    канал или другой пост, и тогда ни id поста, ни ссылка о повторе не скажут.

    Своя сессия на вызов: функция работает в потоке из asyncio.to_thread, а
    requests.Session между потоками делить нельзя — планировщик и /postnow
    вполне могут качать одновременно.
    """
    session = net.new_session()

    for item in items[:MAX_MEDIA_TRIES]:
        data = download_media(item['url'], session=session)
        if data is None:
            continue

        if posted_store.is_content_posted(data.getvalue()):
            logger.info("🧠 Этот файл уже публиковался (совпали байты) — беру следующий")
            continue

        return {'type': item['type'], 'url': item['url'], 'data': data}

    return None


async def _send(media_type: str, data: io.BytesIO) -> None:
    """Отправляет один файл в канал. Ошибки Telegram намеренно наружу: их
    разбирает _publish, чтобы решить, стоит ли перекодировать видео и повторить.
    """
    stamp = int(time.time())

    # BytesIO читается до конца при создании InputFile, поэтому перед каждой
    # попыткой отправки курсор возвращаем в начало
    data.seek(0)

    if media_type == 'video':
        await bot.send_video(
            chat_id=CHANNEL_ID,
            video=InputFile(data, filename=f"meme_{stamp}.mp4"),
            supports_streaming=True,
            read_timeout=SEND_READ_TIMEOUT,
            write_timeout=SEND_WRITE_TIMEOUT,
        )
    else:
        await bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=InputFile(data, filename=f"meme_{stamp}.jpg"),
            read_timeout=SEND_READ_TIMEOUT,
            write_timeout=SEND_WRITE_TIMEOUT,
        )


def _mb(data: io.BytesIO) -> int:
    return len(data.getvalue()) // 1024 // 1024


async def _shrink_video(data: io.BytesIO) -> Tuple[Optional[io.BytesIO], str]:
    """Перекодирует видео через ffmpeg. (None, причина) — не получилось."""
    result = await asyncio.to_thread(convert_video_with_ffmpeg, data.getvalue())
    if result is None:
        return None, "перекодировать видео не удалось (нужен ffmpeg в PATH, см. лог)"

    if len(result.getvalue()) > TELEGRAM_UPLOAD_LIMIT:
        return None, (
            f"после перекодирования видео всё ещё {_mb(result)}МБ, "
            f"предел Telegram — {TELEGRAM_UPLOAD_LIMIT // 1024 // 1024}МБ"
        )

    return result, ""


async def _publish(media_type: str, data: io.BytesIO) -> Tuple[bool, str]:
    """Отправляет один файл. (True, '') — ушёл, иначе (False, причина).

    Причина возвращается наружу, а не только в лог: /postnow отвечает ею
    админу, иначе о провале известно лишь «смотри логи».
    """
    limit_mb = TELEGRAM_UPLOAD_LIMIT // 1024 // 1024
    converted_once = False

    if len(data.getvalue()) > TELEGRAM_UPLOAD_LIMIT:
        if media_type != 'video':
            return False, f"фото весит {_mb(data)}МБ, Bot API принимает не больше {limit_mb}МБ"

        # Раньше такой файл просто пропускался, и пост с тяжёлым видео не
        # публиковался никогда. Сжатие — единственный способ его отправить.
        logger.info(f"🔄 Видео {_mb(data)}МБ больше {limit_mb}МБ, сжимаю через FFmpeg")
        data, reason = await _shrink_video(data)
        if data is None:
            return False, f"видео больше {limit_mb}МБ: {reason}"
        converted_once = True

    try:
        await _send(media_type, data)
        return True, ""
    except (TimedOut, RetryAfter) as e:
        # Повтор не делаем: Telegram мог принять файл и не успеть ответить, а
        # вторая отправка продублировала бы пост в канале.
        return False, f"Telegram не ответил вовремя ({e}) — повтор пропущен, чтобы не задублировать пост"
    except TelegramError as e:
        if media_type != 'video':
            return False, f"Telegram отклонил фото: {e}"
        if converted_once:
            # Второй проход ffmpeg по уже перекодированному файлу — это минуты
            # работы с тем же результатом
            return False, f"Telegram отклонил перекодированное видео: {e}"
        logger.warning(f"⚠️ Telegram не принял видео ({e}), перекодирую через FFmpeg")

    converted, reason = await _shrink_video(data)
    if converted is None:
        return False, f"Telegram отклонил видео, {reason}"

    try:
        await _send(media_type, converted)
        return True, ""
    except (TimedOut, RetryAfter) as e:
        return False, f"Telegram не ответил вовремя на перекодированное видео ({e})"
    except TelegramError as e:
        return False, f"Telegram не принял и перекодированное видео: {e}"


async def _publish_meme(meme: Dict) -> Tuple[bool, str]:
    """Скачивает медиа одного поста и публикует. (True, '') — пост ушёл в канал."""
    source_channel = meme.get('source_channel')
    message_id = meme.get('message_id')
    source_name = meme.get('source_name')

    if not source_channel or not message_id:
        return False, "у выбранного поста нет канала или id — парсер вернул мусор"

    logger.info(f"📥 Обрабатываю мем из {source_name} (ID: {message_id})")

    # Ссылки берём заново: в кэше постов они могли пролежать до часа, а token в
    # url telesco.pe живёт меньше. Кэш — резерв, если страница не открылась.
    items = await asyncio.to_thread(fetch_post_media, source_channel, message_id)
    if not items:
        items = meme.get('media') or []
        if items:
            logger.warning("⚠️ Свежие ссылки получить не удалось, беру из кэша")

    if not items:
        logger.warning(f"⚠️ В посте {message_id} нет медиа, которое можно скачать")
        return False, f"в посте {source_name}/{message_id} нет медиа со ссылкой на файл"

    candidates = pick_candidates(items)
    if not candidates:
        return False, f"все медиа поста {source_name}/{message_id} уже публиковались"

    if len(candidates) > 1:
        logger.info(
            f"🖼️ В посте {len(items)} медиа — публикую одно "
            f"({candidates[0]['type']}), остальные в резерве"
        )

    got = await asyncio.to_thread(download_first, candidates)
    if got is None:
        logger.warning(f"⚠️ Медиа поста {message_id} скачать не удалось")
        return False, (
            f"медиа поста {source_name}/{message_id} не подошло "
            "(не скачалось или уже публиковалось)"
        )

    media_type, data = got['type'], got['data']
    logger.info(f"📤 Отправляю {media_type} ({len(data.getvalue()) // 1024}KB)")

    ok, reason = await _publish(media_type, data)
    if not ok:
        return False, reason

    # Запоминаем только теперь: пост, помеченный до отправки, пропал бы навсегда
    # при любой осечке, ни разу не появившись в канале
    if not await asyncio.to_thread(
        posted_store.remember, source_channel, message_id, got['url'], got['data'].getvalue()
    ):
        logger.warning(
            f"⚠️ Мем опубликован, но записать его в {posted_store.store_path()} "
            "не удалось — после перезапуска он может уйти повторно"
        )

    logger.info(f"✅ Мем из {source_name} опубликован!")
    return True, ""


async def send_meme_to_channel() -> Tuple[bool, str]:
    """Публикует один мем в канал. (True, '') — пост ушёл, иначе (False, причина).

    Перебирает до MAX_CANDIDATES постов: осечка на одном посте не должна
    означать провал всей публикации. Кандидаты берём одним списком — так каждая
    попытка достаётся новому посту (пост помечается опубликованным только после
    успешной отправки, поэтому повторный случайный выбор мог бы вернуть тот же).

    Парсинг, скачивание и транскодирование — синхронные и тяжёлые, поэтому
    уходят в отдельный поток: иначе конвертация видео на минуты замораживала
    весь event loop и бот перестал бы отвечать на команды.
    """
    if not CHANNEL_ID:
        logger.warning("⚠️ CHANNEL_ID не задан — публиковать некуда")
        return False, "CHANNEL_ID не задан в переменных окружения"

    try:
        candidates = await asyncio.to_thread(get_meme_candidates, MAX_CANDIDATES)
    except Exception as e:
        logger.exception("❌ Не удалось выбрать пост с мемом")
        return False, f"не удалось прочитать каналы-источники: {e}"

    if not candidates:
        if not settings.get_meme_channels():
            return False, "список каналов-источников пуст — добавь канал: /sources add <канал>"
        logger.warning("⚠️ Новых мемов не осталось")
        return False, (
            "все посты из каналов-источников уже публиковались. Добавь новые "
            "каналы (/sources add) или разреши повторы (/posted reset)"
        )

    last_reason = ""

    for attempt, meme in enumerate(candidates, 1):
        try:
            ok, last_reason = await _publish_meme(meme)
            if ok:
                return True, ""
        except Exception as e:
            logger.exception(f"❌ Ошибка публикации (кандидат {attempt}/{len(candidates)})")
            last_reason = f"{type(e).__name__}: {e}"

        logger.warning(
            f"⚠️ Кандидат {attempt}/{len(candidates)} не подошёл ({last_reason}), "
            "беру следующий"
        )

    logger.error(f"❌ Ни один из {len(candidates)} постов опубликовать не удалось")
    return False, (
        f"ни один из {len(candidates)} постов не подошёл. Последняя причина: {last_reason}"
    )


async def _post_once() -> bool:
    """Публикация с проверкой режима.

    Планировщик гасит content_supervisor, но между сменой режима и отменой
    задачи есть зазор — попасть в него мем не должен.
    """
    if settings.get_content_mode() != "memes":
        logger.info("ℹ️ Режим уже не memes — публикацию мема пропускаю")
        return False

    ok, reason = await send_meme_to_channel()
    if not ok and reason:
        logger.warning(f"⚠️ Мем не опубликован: {reason}")
    return ok


async def meme_scheduler():
    """Цикл планировщика мемов."""
    channels = settings.get_meme_channels()
    logger.info("=" * 60)
    logger.info("🎬 ПЛАНИРОВЩИК МЕМОВ ЗАПУЩЕН")
    logger.info(f"📡 Канал: {CHANNEL_ID}")
    logger.info(f"⏱️ Интервал: {settings.describe_interval()} (меняется командой /interval)")
    logger.info(f"📦 Источники: {', '.join(channels) if channels else 'не заданы — /sources add'}")
    logger.info("🔄 Видео уходит как есть, FFmpeg — резерв при отказе Telegram")
    logger.info(f"🧠 Повторы: {posted_store.describe()}")
    logger.info("=" * 60)

    count = 0
    interval = random.randint(30, 60)
    logger.info(f"⏳ Первый мем через {interval} секунд...")

    while True:
        # Не asyncio.sleep: /interval должен подействовать сразу, а не через часы
        if await settings.wait_for_next_post(interval):
            interval = settings.next_interval_seconds()
            logger.info(
                f"♻️ Интервал изменён, отсчёт пошёл заново: следующий мем через "
                f"{settings.format_interval(interval)}"
            )
            continue

        if await _post_once():
            count += 1
            interval = settings.next_interval_seconds()
            logger.info(
                f"📊 Всего опубликовано мемов: {count}. Следующий через "
                f"{settings.format_interval(interval)}"
            )
        else:
            interval = RETRY_AFTER_FAILURE
            logger.warning(
                f"⚠️ Публикация не удалась, повтор через {settings.format_interval(interval)}"
            )
