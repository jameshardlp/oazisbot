"""HTTP-эндпоинты для вебхуков платёжных систем.

Оба вызывают mark_order_paid, поэтому кнопка «Проверить оплату» видит
результат сразу. AuraPay подпись не проверяет — см. TODO ниже.
"""
import logging
from aiohttp import web

from .orders import mark_order_paid
from .freekassa import verify_freekassa_webhook_signature

logger = logging.getLogger(__name__)

async def aurapay_webhook(request):
    try:
        data = await request.json()
        logger.info(f"📩 Получен webhook от AuraPay: {data}")

        order_id = data.get('order_id') or data.get('merchant_order_id')
        status = data.get('status') or data.get('payment_status')

        if not order_id:
            return web.Response(text="Missing order_id", status=400)

        # ВНИМАНИЕ: подпись AuraPay здесь не проверяется — эндпоинт открыт,
        # поэтому webhook только помечает заказ, а публикацию по-прежнему
        # запускает кнопка «Проверить оплату» со сверкой через API.
        if status in ['paid', 'success', 'completed']:
            base_order_id = order_id.replace('_aurapay', '')
            mark_order_paid(base_order_id, 'aurapay')

        return web.Response(text="OK", status=200)
    except Exception as e:
        logger.error(f"❌ Ошибка в webhook AuraPay: {e}")
        return web.Response(text="Error", status=500)

async def freekassa_webhook(request):
    try:
        data = dict(await request.post())
        logger.info(f"📩 Получен webhook: {data.get('MERCHANT_ORDER_ID', 'unknown')}")

        if not verify_freekassa_webhook_signature(data):
            return web.Response(text="Invalid signature", status=400)

        order_id = data.get('MERCHANT_ORDER_ID')
        status = data.get('STATUS')

        # FreeKassa не всегда шлёт STATUS: подтверждённая подпись сама по себе
        # означает успешную оплату.
        if status in (None, '', 'SUCCESS', 'success'):
            base_order_id = order_id.replace('_rub', '')
            mark_order_paid(base_order_id, 'rub')

        return web.Response(text="YES", status=200)
    except Exception as e:
        logger.error(f"❌ Ошибка в webhook: {e}")
        return web.Response(text="Error", status=500)
