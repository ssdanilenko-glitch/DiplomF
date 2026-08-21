"""Обработчик feedback отключён в новой архитектуре."""

import logging
from aiogram import Router
from aiogram.types import CallbackQuery

router = Router(name="feedback")
log = logging.getLogger(__name__)


@router.callback_query()
async def on_feedback(cb: CallbackQuery) -> None:
    await cb.answer("Функция обратной связи временно недоступна.", show_alert=True)