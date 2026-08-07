"""Модерация рассылки владельцем и публикация после одобрения."""
import asyncio
import hashlib
import logging
import time

from aiogram.types import (Message, CallbackQuery,
                           InlineKeyboardMarkup, InlineKeyboardButton)

from ...config import OWNER_ID, CHANNEL_ID, SEND_DELAY, MODERATION_DELAY
from ...storage import load_users, save_users
from ...payments.orders import pending_broadcasts
from ..client import bot, dp
from ..media import send_media_message, mark_moderation_card

logger = logging.getLogger(__name__)

async def send_broadcast_for_moderation(broadcast_id: str, broadcast_info: dict):
    if not OWNER_ID:
        return
    try:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"broad_approve_{broadcast_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"broad_reject_{broadcast_id}")
            ]
        ])
        
        text = broadcast_info.get('text', '')
        has_media = broadcast_info.get('has_media', False)
        media_type = broadcast_info.get('media_type')
        media_file_id = broadcast_info.get('media_file_id')
        user_id = broadcast_info.get('user_id')
        payment_type = broadcast_info.get('payment_type', 'stars')
        
        payment_methods = {
            'stars': '⭐ Звёзды',
            'rub': '💳 FreeKassa',
            'aurapay': '🔗 AuraPay'
        }
        payment_method = payment_methods.get(payment_type, '🔗 AuraPay')
        
        preview_text = f"📋 **Новая рассылка на модерацию** #{broadcast_id}\n\n"
        preview_text += f"👤 Заказчик ID: {user_id}\n"
        preview_text += f"💰 Оплачено: {payment_method}\n"
        
        if text:
            preview_text += f"\n📝 Текст:\n{text[:500]}{'...' if len(text) > 500 else ''}\n"
        else:
            preview_text += f"\n📝 Текст: (без текста)\n"
        
        if has_media:
            media_names = {
                "photo": "📸 Фото",
                "video": "🎬 Видео",
                "document": "📄 Документ",
                "animation": "🎥 GIF",
                "audio": "🎵 Аудио",
                "voice": "🎤 Голосовое",
                "video_note": "🔄 Видео-кружок",
                "sticker": "🎯 Стикер"
            }
            preview_text += f"\n📎 {media_names.get(media_type, 'Медиафайл')} (будет отправлено)\n"
        
        preview_text += f"\n⏳ После подтверждения будет задержка 5 минут перед публикацией."
        
        if has_media and media_file_id:
            await send_media_message(OWNER_ID, media_type, media_file_id,
                                     caption=preview_text, reply_markup=keyboard,
                                     parse_mode="Markdown")
        else:
            await bot.send_message(
                chat_id=OWNER_ID,
                text=preview_text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )

        logger.info(f"📨 Рассылка {broadcast_id} на модерации")
    except Exception as e:
        logger.error(f"Ошибка модерации: {e}")

@dp.callback_query(lambda c: c.data and c.data.startswith('broad_'))
async def handle_broadcast_moderation(callback: CallbackQuery):
    try:
        if callback.from_user.id != OWNER_ID:
            await callback.answer("⛔ Доступ запрещен", show_alert=True)
            return
        parts = callback.data.split('_')
        action = parts[1]
        broadcast_id = '_'.join(parts[2:])
        approved = action == 'approve'
        if broadcast_id not in pending_broadcasts:
            await callback.answer("❌ Сообщение не найдено", show_alert=True)
            return
        broadcast_info = pending_broadcasts[broadcast_id]
        if approved:
            await callback.answer("✅ Сообщение одобрено. Будет опубликовано через 5 минут.", show_alert=True)
            await mark_moderation_card(callback.message, "\n\n✅ ОДОБРЕНО")
            await asyncio.sleep(300)
            if broadcast_id in pending_broadcasts:
                text = broadcast_info.get('text', '')
                has_media = broadcast_info.get('has_media', False)
                media_type = broadcast_info.get('media_type')
                media_file_id = broadcast_info.get('media_file_id')

                users_list = load_users()
                sent_count = 0
                failed_count = 0

                for i, chat_id in enumerate(users_list):
                    try:
                        if has_media and media_file_id:
                            await send_media_message(chat_id, media_type, media_file_id, caption=text)
                        elif text:
                            await bot.send_message(chat_id=chat_id, text=text)

                        sent_count += 1

                        if i < len(users_list) - 1:
                            await asyncio.sleep(SEND_DELAY)

                    except Exception as e:
                        logger.error(f"Ошибка отправки в {chat_id}: {e}")
                        failed_count += 1
                        if "forbidden" in str(e).lower() or "chat not found" in str(e).lower():
                            fresh_users = load_users()
                            if chat_id in fresh_users:
                                fresh_users.remove(chat_id)
                                save_users(fresh_users)
                
                try:
                    if CHANNEL_ID and CHANNEL_ID.strip():
                        if has_media and media_file_id:
                            await send_media_message(CHANNEL_ID, media_type, media_file_id, caption=text)
                        elif text:
                            await bot.send_message(chat_id=CHANNEL_ID, text=text)
                        logger.info(f"📢 Отправлено в канал {CHANNEL_ID}")
                except Exception as e:
                    logger.error(f"Ошибка отправки в канал: {e}")
                
                del pending_broadcasts[broadcast_id]
                
                try:
                    await bot.send_message(
                        chat_id=OWNER_ID,
                        text=f"📊 Рассылка #{broadcast_id} завершена!\n"
                             f"✅ Отправлено: {sent_count}\n"
                             f"❌ Ошибок: {failed_count}\n"
                             f"📝 {text[:200]}{'...' if len(text) > 200 else ''}\n"
                             f"{'📎 С медиафайлом' if has_media else ''}"
                    )
                except Exception as e:
                    logger.error(f"Ошибка отправки отчета: {e}")
                
                try:
                    user_id = broadcast_info.get('user_id')
                    if user_id:
                        await bot.send_message(
                            chat_id=user_id,
                            text=f"✅ Ваше сообщение опубликовано!\n"
                                 f"📨 Отправлено: {sent_count} пользователям\n"
                                 f"📝 {text[:100]}{'...' if len(text) > 100 else ''}\n"
                                 f"{'📎 С медиафайлом' if has_media else ''}"
                        )
                except Exception as e:
                    logger.error(f"Ошибка уведомления заказчика: {e}")
        else:
            await callback.answer("❌ Сообщение отклонено", show_alert=True)
            await callback.message.edit_text(
                callback.message.text + "\n\n❌ ОТКЛОНЕНО",
                reply_markup=None
            )
            try:
                user_id = broadcast_info.get('user_id')
                if user_id:
                    await bot.send_message(
                        chat_id=user_id,
                        text="❌ Ваше сообщение отклонено модератором."
                    )
            except Exception as e:
                logger.error(f"Ошибка уведомления заказчика: {e}")
            if broadcast_id in pending_broadcasts:
                del pending_broadcasts[broadcast_id]
    except Exception as e:
        logger.error(f"Ошибка в broadcast модерации: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)
