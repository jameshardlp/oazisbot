"""Оплата рассылки: Telegram Stars, рубли (FreeKassa), AuraPay."""
import hashlib
import logging
import time

from aiogram.types import (CallbackQuery, PreCheckoutQuery, Message,
                           InlineKeyboardMarkup, InlineKeyboardButton,
                           LabeledPrice, WebAppInfo)

from config import OWNER_ID, AURAPAY_MINIAPP_URL
from payments.orders import broadcast_data, broadcast_prices, pending_broadcasts
from payments.freekassa import create_freekassa_payment_link, check_freekassa_payment_status
from payments.aurapay import check_aurapay_payment_status
from client import bot, dp
from moderation import send_broadcast_for_moderation

logger = logging.getLogger(__name__)

@dp.callback_query(lambda c: c.data and c.data.startswith('pay_stars_'))
async def pay_with_stars(callback: CallbackQuery):
    try:
        order_id = callback.data.replace('pay_stars_', '')
        user_id = callback.from_user.id
        
        if user_id not in broadcast_data:
            await callback.answer("❌ Данные не найдены", show_alert=True)
            return
        
        broadcast_info = broadcast_data[user_id]
        if broadcast_info.get('order_id') != order_id:
            await callback.answer("❌ Неверный заказ", show_alert=True)
            return
        
        text = broadcast_info.get('text', '')
        has_media = broadcast_info.get('has_media', False)
        stars_price = broadcast_prices.get("stars", 100)
        
        description = f"Отправка сообщения всем подписчикам бота"
        if text:
            description += f"\n\nТекст: {text[:100]}{'...' if len(text) > 100 else ''}"
        if has_media:
            description += "\n📎 С медиафайлом"
        
        prices = [LabeledPrice(label="⭐ Рассылка", amount=stars_price)]
        
        await bot.send_invoice(
            chat_id=user_id,
            title="📢 Рассылка сообщения",
            description=description,
            payload=f"broadcast_stars_{order_id}",
            provider_token="",
            currency="XTR",
            prices=prices,
            start_parameter="broadcast",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"⭐ Оплатить {stars_price} звёзд", pay=True)]
            ])
        )
        
        await callback.answer("🔄 Отправлен счёт на оплату звёздами")
    except Exception as e:
        logger.error(f"Ошибка оплаты звёздами: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@dp.callback_query(lambda c: c.data and c.data.startswith('pay_rub_'))
async def pay_with_rub(callback: CallbackQuery):
    try:
        order_id = callback.data.replace('pay_rub_', '')
        user_id = callback.from_user.id
        
        if user_id not in broadcast_data:
            await callback.answer("❌ Данные не найдены", show_alert=True)
            return
        
        broadcast_info = broadcast_data[user_id]
        if broadcast_info.get('order_id') != order_id:
            await callback.answer("❌ Неверный заказ", show_alert=True)
            return
        
        text = broadcast_info.get('text', '')
        has_media = broadcast_info.get('has_media', False)
        rub_price = broadcast_prices.get("rub", 100)
        
        description = f"Рассылка в Telegram"
        if text:
            description += f": {text[:50]}"
        
        payment_url = create_freekassa_payment_link(
            rub_price,
            f"{order_id}_rub",
            description
        )
        
        if not payment_url:
            await callback.answer("❌ FreeKassa не настроен", show_alert=True)
            return
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💳 Оплатить {rub_price} RUB", url=payment_url)],
            [InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"check_rub_payment_{order_id}")]
        ])
        
        preview_text = f"💳 **Оплата в рублях**\n\n"
        if text:
            preview_text += f"📝 Текст: {text[:100]}{'...' if len(text) > 100 else ''}\n"
        else:
            preview_text += f"📝 (без текста)\n"
        if has_media:
            preview_text += f"📎 С медиафайлом\n"
        preview_text += f"💰 Сумма: {rub_price} RUB\n\n"
        preview_text += f"🔗 Нажмите кнопку ниже для оплаты через FreeKassa.\n"
        preview_text += f"После оплаты нажмите 'Проверить оплату'."
        
        await callback.message.edit_text(
            preview_text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
        await callback.answer("🔄 Ссылка на оплату создана")
    except Exception as e:
        logger.error(f"Ошибка оплаты рублями: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@dp.callback_query(lambda c: c.data and c.data.startswith('pay_aurapay_'))
async def pay_with_aurapay(callback: CallbackQuery):
    try:
        order_id = callback.data.replace('pay_aurapay_', '')
        user_id = callback.from_user.id
        
        if user_id not in broadcast_data:
            await callback.answer("❌ Данные не найдены", show_alert=True)
            return
        
        broadcast_info = broadcast_data[user_id]
        if broadcast_info.get('order_id') != order_id:
            await callback.answer("❌ Неверный заказ", show_alert=True)
            return
        
        rub_price = broadcast_prices.get("rub", 100)
        
        miniapp_url = f"{AURAPAY_MINIAPP_URL}?order_id={order_id}&user_id={user_id}&amount={rub_price}&currency=RUB"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Оплатить через AuraPay", web_app=WebAppInfo(url=miniapp_url))],
            [InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"check_aurapay_payment_{order_id}")]
        ])
        
        text = broadcast_info.get('text', '')
        has_media = broadcast_info.get('has_media', False)
        
        preview_text = f"🔗 **Оплата через AuraPay**\n\n"
        if text:
            preview_text += f"📝 Текст: {text[:100]}{'...' if len(text) > 100 else ''}\n"
        if has_media:
            preview_text += f"📎 С медиафайлом\n"
        preview_text += f"💰 Сумма: {rub_price} RUB\n\n"
        preview_text += f"🔐 Нажмите кнопку ниже для оплаты через AuraPay.\n"
        preview_text += f"После оплаты нажмите 'Проверить оплату'."
        
        await callback.message.edit_text(
            preview_text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
        await callback.answer("🔄 Ссылка на AuraPay создана")
        
    except Exception as e:
        logger.error(f"Ошибка оплаты через AuraPay: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@dp.callback_query(lambda c: c.data and c.data.startswith('check_rub_payment_'))
async def check_rub_payment(callback: CallbackQuery):
    try:
        order_id = callback.data.replace('check_rub_payment_', '')
        user_id = callback.from_user.id
        
        if user_id not in broadcast_data:
            await callback.answer("❌ Данные не найдены", show_alert=True)
            return
        
        broadcast_info = broadcast_data[user_id]
        if broadcast_info.get('order_id') != order_id:
            await callback.answer("❌ Неверный заказ", show_alert=True)
            return
        
        await callback.answer("⏳ Проверяю статус платежа...")

        # Сначала вебхук: он приходит раньше, чем ответит статус-API.
        paid = broadcast_info.get('paid') is True

        payment_status = await check_freekassa_payment_status(f"{order_id}_rub")

        if paid or (payment_status and payment_status.get('status') == 'paid'):
            await process_successful_payment_broadcast(user_id, broadcast_info, "rub")
            await callback.message.answer(
                "✅ Оплата подтверждена!\n\n"
                "Ваше сообщение отправлено на модерацию.\n"
                "Ожидайте подтверждения от администратора."
            )
        else:
            await callback.message.answer(
                "❌ Платёж ещё не оплачен.\n"
                "Оплатите счёт и нажмите 'Проверить оплату' снова."
            )
    except Exception as e:
        logger.error(f"Ошибка проверки оплаты: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@dp.callback_query(lambda c: c.data and c.data.startswith('check_aurapay_payment_'))
async def check_aurapay_payment(callback: CallbackQuery):
    try:
        order_id = callback.data.replace('check_aurapay_payment_', '')
        user_id = callback.from_user.id
        
        if user_id not in broadcast_data:
            await callback.answer("❌ Данные не найдены", show_alert=True)
            return
        
        broadcast_info = broadcast_data[user_id]
        if broadcast_info.get('order_id') != order_id:
            await callback.answer("❌ Неверный заказ", show_alert=True)
            return
        
        await callback.answer("⏳ Проверяю статус платежа...")

        full_order_id = f"{order_id}_aurapay"

        # Сначала вебхук: он приходит раньше, чем ответит статус-API.
        paid = broadcast_info.get('paid') is True

        payment_status = await check_aurapay_payment_status(full_order_id)

        if paid or (payment_status and payment_status.get('status') in ['paid', 'success', 'completed']):
            await process_successful_payment_broadcast(user_id, broadcast_info, "aurapay")
            await callback.message.answer(
                "✅ Оплата через AuraPay подтверждена!\n\n"
                "Ваше сообщение отправлено на модерацию.\n"
                "Ожидайте подтверждения от администратора."
            )
        else:
            await callback.message.answer(
                "❌ Платёж ещё не оплачен.\n"
                "Оплатите счёт и нажмите 'Проверить оплату' снова."
            )
            
    except Exception as e:
        logger.error(f"Ошибка проверки оплаты AuraPay: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    try:
        if pre_checkout_query.invoice_payload.startswith("broadcast_stars_"):
            await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
        else:
            await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=False, error_message="Неизвестный платёж")
    except Exception as e:
        logger.error(f"Ошибка в pre_checkout: {e}")
        await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=False, error_message="Ошибка")

@dp.message(lambda message: message.successful_payment is not None)
async def process_successful_payment(message: Message):
    try:
        user_id = message.from_user.id
        payload = message.successful_payment.invoice_payload
        if not payload.startswith("broadcast_stars_"):
            return
        
        order_id = payload.replace("broadcast_stars_", "")
        
        broadcast_info = broadcast_data.get(user_id)
        if not broadcast_info:
            await message.answer("❌ Данные о сообщении не найдены. Попробуйте снова.")
            return
        
        await process_successful_payment_broadcast(user_id, broadcast_info, "stars")
    except Exception as e:
        logger.error(f"Ошибка в successful_payment: {e}")
        await message.answer(f"❌ Ошибка при обработке платежа: {str(e)}")

async def process_successful_payment_broadcast(user_id: int, broadcast_info: dict, payment_type: str):
    try:
        text = broadcast_info.get('text', '')
        has_media = broadcast_info.get('has_media', False)
        media_type = broadcast_info.get('media_type')
        media_file_id = broadcast_info.get('media_file_id')
        
        if not text and not has_media:
            return
        
        broadcast_id = f"broadcast_{int(time.time())}_{hashlib.md5(str(broadcast_info).encode()).hexdigest()[:8]}"
        
        pending_broadcasts[broadcast_id] = {
            'text': text,
            'has_media': has_media,
            'media_type': media_type,
            'media_file_id': media_file_id,
            'user_id': user_id,
            'timestamp': time.time(),
            'chat_id': broadcast_info.get('chat_id'),
            'payment_type': payment_type
        }
        
        if user_id in broadcast_data:
            del broadcast_data[user_id]
        
        await send_broadcast_for_moderation(broadcast_id, pending_broadcasts[broadcast_id])
        
        payment_methods = {
            'stars': '⭐ Звёзды',
            'rub': '💳 FreeKassa',
            'aurapay': '🔗 AuraPay'
        }
        payment_method = payment_methods.get(payment_type, '🔗 AuraPay')
        
        await bot.send_message(
            chat_id=user_id,
            text=f"✅ Оплата получена! Сообщение отправлено на модерацию.\n"
                 f"📝 {text[:100]}{'...' if len(text) > 100 else ''}\n"
                 f"{'📎 С медиафайлом' if has_media else ''}\n"
                 f"💳 Способ оплаты: {payment_method}\n\n"
                 f"⏳ Ожидайте подтверждения от администратора."
        )
    except Exception as e:
        logger.error(f"Ошибка обработки оплаты: {e}")
