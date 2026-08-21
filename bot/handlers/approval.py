"""Обработчик инлайн-кнопок для подтверждения опасных действий."""

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.services.backend_client import BackendClient
from bot.handlers.text import pending_approvals

router = Router(name="approval")
log = logging.getLogger(__name__)

@router.callback_query(F.data.in_(["approve_yes", "approve_no"]))
async def on_approval(cb: CallbackQuery, backend: BackendClient) -> None:
    user_id = str(cb.message.chat.id)
    thread_id = pending_approvals.pop(user_id, None)
    if not thread_id:
        await cb.answer("⚠️ Нет активного запроса на подтверждение.")
        return

    resume_value = (cb.data == "approve_yes")
    try:
        result = await backend.resume_agent(thread_id, resume_value, platform="telegram")
        # Удаляем кнопки
        await cb.message.edit_reply_markup(reply_markup=None)
        # Отправляем результат
        await cb.message.answer(result.get("answer", "Готово."))
        await cb.answer()
    except Exception as e:
        log.exception("Resume failed")
        await cb.message.answer(f"❌ Ошибка: {e}")
        await cb.answer()