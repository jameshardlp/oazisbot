async def main() -> None:
    """Основная асинхронная функция."""
    logger.info("=" * 60)
    logger.info("🤖 БОТ ЗАПУЩЕН")
    logger.info("📸 Посты про стримеров (текст + ссылки на YouTube)")
    logger.info("🎬 Мемы из каналов (скачивание и отправка)")
    logger.info("📦 Источники мемов: videos_dolboyoba, shitcollection, postleftism, noviop")
    logger.info("📤 Команда /resend — отправка контента в канал от имени бота")
    logger.info("=" * 60)

    # Запускаем webhook сервер
    web_app = web.Application()
    if FREEKASSA_SHOP_ID and FREEKASSA_SECRET1:
        await start_webhook_server(web_app)

    # Удаляем вебхук перед запуском (чтобы избежать конфликтов)
    try:
        await application.bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Вебхук удалён")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка удаления вебхука: {e}")

    # Регистрируем ВСЕ обработчики команд
    register_admin_handlers(application)
    register_basic_handlers(application)

    # Добавляем обработчик для /broadcast (реклама)
    broadcast_handler = get_broadcast_conversation_handler()
    application.add_handler(broadcast_handler)
    application.add_handler(CallbackQueryHandler(broadcast_callback, pattern="^(pay_with_stars|pay_with_card|cancel_broadcast|cancel_stars_payment)$"))

    # Добавляем обработчик для /resend (ручная отправка в канал)
    resend_handler = get_resend_conversation_handler()
    application.add_handler(resend_handler)

    # Запускаем планировщик стримеров как фоновую задачу
    scheduler_task = asyncio.create_task(scheduler())
    
    # Запускаем планировщик мемов как фоновую задачу
    meme_scheduler_task = asyncio.create_task(meme_scheduler())

    try:
        # Запускаем бота
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        logger.info("✅ Бот запущен и готов к работе")
        
        # Ждём сигнала остановки
        await asyncio.Event().wait()
        
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("🛑 Получен сигнал остановки")
    finally:
        # Корректно завершаем задачи
        logger.info("🔄 Завершаем работу...")
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
        
        # Отменяем фоновые задачи
        scheduler_task.cancel()
        meme_scheduler_task.cancel()
        
        await shutdown_tasks()
        logger.info("✅ Бот остановлен")
