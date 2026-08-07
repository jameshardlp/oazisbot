"""Импорт этого пакета регистрирует все хендлеры в dispatcher.

Хендлеры навешиваются декораторами @dp.* на этапе импорта, поэтому модули
нужно импортировать до старта polling — даже если имена не используются напрямую.
"""
from . import basic, admin, broadcast, payment, moderation  # noqa: F401

__all__ = ["basic", "admin", "broadcast", "payment", "moderation"]
