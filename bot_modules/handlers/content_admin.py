"""Админские команды управления контентом: /mode, /interval, /postnow, /sources.

Ответы намеренно без parse_mode: имена каналов содержат подчёркивания
(videos_dolboyoba), и в режиме Markdown Telegram либо отвергнет сообщение,
либо съест часть текста.
"""
import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

import settings
from config import CHANNEL_ID, is_admin
from content import meme_forwarder, posted_store
from bot_modules.meme_scheduler import send_meme_to_channel

logger = logging.getLogger(__name__)

MODE_USAGE = (
    "Как переключить:\n"
    "/mode streamers — посты про стримеров\n"
    "/mode memes — мемы из каналов-источников\n"
    "Одновременно работает ровно один режим."
)

INTERVAL_USAGE = (
    "Как задать:\n"
    "/interval 90 — ровно 90 минут между постами\n"
    "/interval 60 180 — случайно от 60 до 180 минут\n"
    f"Допустимо от {settings.MIN_ALLOWED_MINUTES} до {settings.MAX_ALLOWED_MINUTES} минут."
)

SOURCES_USAGE = (
    "Управление списком:\n"
    "/sources add <канал> [канал ...] — добавить\n"
    "/sources del <канал> [канал ...] — убрать\n"
    "/sources reset — вернуть список по умолчанию"
)

# /postnow работает минуты (скачивание + FFmpeg), поэтому запускается отдельной
# задачей. Флаг ставится синхронно в самом хендлере: между проверкой и
# присваиванием нет await, так что два /postnow подряд не разъедутся.
_posting_now = False
# Без своей ссылки задачу может собрать сборщик мусора прямо во время работы
_background_tasks = set()


async def _require_owner(update: Update) -> bool:
    """Пускает дальше только владельца (см. ADMIN_IDS в config). Сам объясняет отказ."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав.")
        return False

    return True


# ===== /mode =====

async def mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает или переключает режим контента без перезапуска бота."""
    if not await _require_owner(update):
        return

    args = context.args or []

    if not args:
        # Заодно показываем, откуда взят режим: если файл настроек пропал, это
        # первый признак того, что /mode откатился при перезапуске
        await update.message.reply_text(
            f"🔀 Текущий режим: {settings.describe_content_mode()}\n"
            f"💾 Настройки: {settings.describe_storage()}\n\n{MODE_USAGE}"
        )
        return

    if len(args) > 1:
        await update.message.reply_text(f"⚠️ Ожидаю один режим.\n\n{MODE_USAGE}")
        return

    mode = args[0].strip().lower().lstrip("/")

    # Синонимы: подсказки в /help называют режимы точно, но «мемы» руками набрать
    # проще, чем переключаться на латиницу
    aliases = {
        "memes": "memes", "meme": "memes", "мемы": "memes", "мем": "memes",
        "streamers": "streamers", "streamer": "streamers",
        "стримеры": "streamers", "стример": "streamers",
    }
    mode = aliases.get(mode, mode)

    if mode not in settings.CONTENT_MODES:
        await update.message.reply_text(
            f"⚠️ Неизвестный режим: {args[0]}\n\n{MODE_USAGE}"
        )
        return

    if mode == settings.get_content_mode():
        await update.message.reply_text(
            f"ℹ️ Режим уже такой: {settings.describe_content_mode()}"
        )
        return

    ok = settings.set_content_mode(mode)

    lines = [
        f"✅ Режим переключён: {settings.describe_content_mode()}",
        # Оба планировщика после старта ждут 10-60 секунд и публикуют первый пост
        "♻️ Планировщик перезапущен: первый пост примерно через минуту, "
        f"дальше — раз в {settings.describe_interval()}.",
    ]

    if mode == "memes" and not settings.get_meme_channels():
        lines.append(
            "⚠️ Список каналов-источников пуст — мемы брать неоткуда. "
            "Добавь канал: /sources add <канал>"
        )

    if not ok:
        lines.append(
            "⚠️ Не удалось записать настройки в файл — после перезапуска "
            "вернётся прежний режим."
        )
    elif mode == "memes":
        # Режим лежит в файле рядом с ботом. На хостингах с эфемерным диском он
        # исчезает при перезапуске, и бот возвращается к CONTENT_MODE —
        # выглядит как «сам переключился обратно на стримеров».
        lines.append(
            "ℹ️ Режим записан в файл. Если после перезапуска бот снова начнёт "
            "постить стримеров — задай CONTENT_MODE=memes в переменных "
            "окружения хостинга: файл настроек там не сохраняется."
        )

    await update.message.reply_text("\n".join(lines))


# ===== /interval =====

async def interval_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает или задаёт интервал между автоматическими постами."""
    if not await _require_owner(update):
        return

    args = context.args or []

    if not args:
        await update.message.reply_text(
            f"⏱️ Текущий интервал: {settings.describe_interval()}\n\n{INTERVAL_USAGE}"
        )
        return

    if len(args) > 2:
        await update.message.reply_text(f"⚠️ Ожидаю одно или два числа.\n\n{INTERVAL_USAGE}")
        return

    try:
        values = [int(a) for a in args]
    except ValueError:
        await update.message.reply_text(
            f"⚠️ Интервал задаётся целыми числами (минуты).\n\n{INTERVAL_USAGE}"
        )
        return

    lo, hi = (values[0], values[0]) if len(values) == 1 else (values[0], values[1])

    notes = []
    if lo > hi:
        lo, hi = hi, lo
        notes.append("ℹ️ Границы были перевёрнуты, поменял местами.")

    if lo < settings.MIN_ALLOWED_MINUTES or hi > settings.MAX_ALLOWED_MINUTES:
        await update.message.reply_text(
            f"⚠️ Допустимо от {settings.MIN_ALLOWED_MINUTES} до "
            f"{settings.MAX_ALLOWED_MINUTES} минут (неделя).\n\n{INTERVAL_USAGE}"
        )
        return

    if lo < settings.FLOOD_WARNING_MINUTES:
        notes.append(
            f"⚠️ Меньше {settings.FLOOD_WARNING_MINUTES} минут — Telegram может "
            "начать ограничивать публикации в канале."
        )

    if not settings.set_interval_minutes(lo, hi):
        notes.append("⚠️ Не удалось записать настройки в файл — после перезапуска вернётся прежнее значение.")

    lines = [
        f"✅ Интервал: {settings.describe_interval()}",
        "♻️ Отсчёт до следующего поста начат заново.",
    ]
    lines.extend(notes)
    await update.message.reply_text("\n".join(lines))


# ===== /postnow =====

async def _post_now_job(chat_id: int, bot) -> None:
    """Публикует мем и присылает результат владельцу отдельным сообщением."""
    global _posting_now
    try:
        ok, reason = await send_meme_to_channel()
        if ok:
            text = "✅ Мем опубликован в канале."
        else:
            text = f"❌ Опубликовать не удалось: {reason}"
    except Exception as e:
        logger.error(f"❌ Ошибка внеплановой публикации: {e}")
        text = f"❌ Ошибка при публикации: {e}"
    finally:
        _posting_now = False

    try:
        await bot.send_message(chat_id=chat_id, text=text)
    except Exception as e:
        logger.error(f"❌ Не удалось отправить результат /postnow: {e}")


async def postnow_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Публикует мем из каналов-источников немедленно, вне расписания."""
    global _posting_now

    if not await _require_owner(update):
        return

    if _posting_now:
        await update.message.reply_text("⏳ Публикация уже идёт, подожди её окончания.")
        return

    if not settings.get_meme_channels():
        await update.message.reply_text(
            "⚠️ Список каналов-источников пуст — брать мем неоткуда.\n\n" + SOURCES_USAGE
        )
        return

    if not CHANNEL_ID:
        await update.message.reply_text(
            "⚠️ CHANNEL_ID не задан в конфиге — публиковать некуда."
        )
        return

    # Флаг ставим до первого await: иначе два /postnow успели бы проскочить
    # проверку выше и полезли бы в канал одновременно
    _posting_now = True
    try:
        await update.message.reply_text(
            "🚀 Беру мем из каналов-источников. Это может занять пару минут "
            "(скачивание и перекодирование видео).\n"
            "Таймер планировщика при этом не сдвигается."
        )
    except Exception as e:
        # Публикацию всё равно запускаем — результат придёт вторым сообщением
        logger.warning(f"⚠️ Не удалось подтвердить /postnow: {e}")

    task = asyncio.create_task(_post_now_job(update.effective_chat.id, context.bot))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


# ===== /sources =====

def _sources_list_text() -> str:
    channels = settings.get_meme_channels()
    if not channels:
        return "📦 Каналы-источники: список пуст, мемы брать неоткуда.\n\n" + SOURCES_USAGE

    listing = "\n".join(f"{i}. {name}" for i, name in enumerate(channels, 1))
    return f"📦 Каналы-источники ({len(channels)}):\n{listing}\n\n{SOURCES_USAGE}"


async def _add_sources(raw_names) -> tuple:
    """Добавляет каналы. Возвращает (строки отчёта, было ли изменение)."""
    lines = []
    changed = False

    for raw in raw_names:
        name = settings.normalize_channel(raw)
        if not name:
            lines.append(f"❌ {raw} — не похоже на имя канала")
            continue

        if name in settings.get_meme_channels():
            lines.append(f"• {name} — уже в списке")
            continue

        # Проверка ходит в сеть, поэтому в отдельном потоке
        found = await asyncio.to_thread(meme_forwarder.check_channel, name)
        settings.add_meme_channel(name)
        changed = True

        if found is None:
            lines.append(
                f"⚠️ {name} — добавлен, но прочитать канал не удалось "
                "(закрыт, не существует или t.me не ответил)"
            )
        elif found == 0:
            lines.append(f"⚠️ {name} — добавлен, но постов с медиа в нём не видно")
        else:
            lines.append(f"✅ {name} — добавлен, постов с медиа: {found}")

    return lines, changed


def _remove_sources(raw_names) -> tuple:
    """Убирает каналы. Возвращает (строки отчёта, было ли изменение)."""
    lines = []
    changed = False

    for raw in raw_names:
        name = settings.normalize_channel(raw)
        if not name:
            lines.append(f"❌ {raw} — не похоже на имя канала")
            continue

        if settings.remove_meme_channel(name):
            lines.append(f"✅ {name} — убран")
            changed = True
        else:
            lines.append(f"• {name} — его не было в списке")

    return lines, changed


async def sources_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает и правит список каналов, из которых берутся мемы."""
    if not await _require_owner(update):
        return

    args = context.args or []

    if not args:
        await update.message.reply_text(_sources_list_text())
        return

    action = args[0].lower()
    rest = args[1:]

    if action == "add":
        if not rest:
            await update.message.reply_text(f"⚠️ Укажи хотя бы один канал.\n\n{SOURCES_USAGE}")
            return
        lines, changed = await _add_sources(rest)

    elif action in ("del", "delete", "remove", "rm"):
        if not rest:
            await update.message.reply_text(f"⚠️ Укажи хотя бы один канал.\n\n{SOURCES_USAGE}")
            return
        lines, changed = _remove_sources(rest)

    elif action == "reset":
        settings.reset_meme_channels()
        lines, changed = ["✅ Список каналов сброшен к значениям по умолчанию"], True

    else:
        await update.message.reply_text(
            f"⚠️ Неизвестное действие: {action}\n\n{SOURCES_USAGE}"
        )
        return

    if changed:
        # Иначе новый список подхватился бы только после истечения cache_ttl (час)
        meme_forwarder.invalidate_cache()

    if not settings.get_meme_channels():
        lines.append(
            "⚠️ Список пуст — планировщик мемов больше ничего не найдёт. "
            "Добавь канал или сделай /sources reset."
        )

    await update.message.reply_text("\n".join(lines) + "\n\n" + _sources_list_text())


def register_content_admin_handlers(app):
    """Регистрирует команды управления контентом."""
    app.add_handler(CommandHandler("mode", mode_command))
    app.add_handler(CommandHandler("interval", interval_command))
    app.add_handler(CommandHandler("postnow", postnow_command))
    app.add_handler(CommandHandler("sources", sources_command))
