"""FSM-сценарий /ask: выбор темы → текст вопроса → отправка с topic-префиксом."""

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.inline import topics_kb
from bot.services.error_handling import handle_backend_error
from bot.states import AskFlow
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.services.backend_client import BackendClient
from bot.handlers.text import pending_approvals

router = Router(name="fsm")
log = logging.getLogger(__name__)


@router.message(Command("ask"))
async def cmd_ask(message: Message, state: FSMContext) -> None:
    await state.set_state(AskFlow.waiting_for_topic)
    await message.answer("Выберите тему:", reply_markup=topics_kb())


@router.callback_query(F.data.startswith("topic:"), AskFlow.waiting_for_topic)
async def on_topic_selected(cb: CallbackQuery, state: FSMContext) -> None:
    _, slug = cb.data.split(":", 1)
    if slug == "cancel":
        await state.clear()
        if cb.message is not None:
            await cb.message.edit_text("Отменено.")
        await cb.answer()
        return
    await state.update_data(topic=slug)
    await state.set_state(AskFlow.waiting_for_question)
    if cb.message is not None:
        await cb.message.edit_text(
            f"Тема: {slug}\nЗадайте ваш вопрос текстом."
        )
    await cb.answer()


@router.message(AskFlow.waiting_for_question, F.text)
async def on_question_received(
    message: Message,
    backend: BackendClient,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    topic = data.get("topic", "general")
    prompt = f"Тема: {topic}. Вопрос: {message.text}"

    try:
        result = await backend.process_message(
            user_id=str(message.chat.id),
            chat_id=str(message.chat.id),
            text=prompt,
            platform="telegram",
        )

        answer = result.get("answer", "")
        if result.get("need_approval"):
            thread_id = result.get("thread_id")
            if thread_id:
                pending_approvals[str(message.chat.id)] = thread_id
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Да", callback_data="approve_yes"),
                        InlineKeyboardButton(text="❌ Нет", callback_data="approve_no"),
                    ]
                ])
                await message.answer(answer, reply_markup=kb)
                await state.clear()
                return

        await message.answer(answer)
        for attachment in result.get("attachments", []):
            await message.answer(attachment)
        await state.clear()
    except Exception as exc:
        await handle_backend_error(message, exc)
        await state.clear()