"""Обработчик свободного текста (catch-all) через агента."""

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from bot.services.backend_client import BackendClient
from bot.services.error_handling import handle_backend_error

router = Router(name="text")
log = logging.getLogger(__name__)

# Хранилище для ожидающих подтверждений (thread_id -> user_id)
# В реальном проекте лучше использовать Redis, но для демо подойдёт словарь.
pending_approvals = {}

@router.message(F.text & ~F.text.startswith("/"))
async def on_text(
    message: Message,
    backend: BackendClient,
    state: FSMContext,
) -> None:
    if await state.get_state() is not None:
        return  # если FSM активен, не обрабатываем

    try:
        result = await backend.process_message(
            user_id=str(message.chat.id),
            chat_id=str(message.chat.id),
            text=message.text,
            platform="telegram",
        )

        answer = result.get("answer", "")

        # Проверяем, требуется ли подтверждение
        if result.get("need_approval"):
            thread_id = result.get("thread_id")
            if thread_id:
                # Сохраняем thread_id для последующего resume
                pending_approvals[str(message.chat.id)] = thread_id
                # Показываем кнопки "Да / Нет"
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Да", callback_data="approve_yes"),
                        InlineKeyboardButton(text="❌ Нет", callback_data="approve_no"),
                    ]
                ])
                await message.answer(answer, reply_markup=kb)
                return

        # Если нет подтверждения — просто отправляем ответ
        await message.answer(answer)

        # Если есть вложения — отправляем их
        for attachment in result.get("attachments", []):
            await message.answer(attachment)

    except Exception as exc:
        await handle_backend_error(message, exc)