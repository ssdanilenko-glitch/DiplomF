"""Команды бота: /start, /help, /clear, /cancel."""

import logging
from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.services.backend_client import BackendClient

router = Router(name="commands")
log = logging.getLogger(__name__)

@router.message(CommandStart())
@router.message(CommandStart())
async def cmd_start(
    message: Message, state: FSMContext
) -> None:
    await state.clear()
    try:
        log.info(f"Обработчик /start вызван для пользователя {message.from_user.id}")
        await message.answer(
            "Привет! Я подключён к ИИ-агенту. Пиши сообщения — я отвечу.\n"
            "Команды: /help, /ask, /cancel"
        )
        log.info(f"Ответ на /start отправлен пользователю {message.from_user.id}")
    except Exception as e:
        log.exception(f"Ошибка при отправке /start: {e}")

@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Доступные команды:\n"
        "/start — начать заново\n"
        "/ask — задать вопрос с выбором темы\n"
        "/cancel — отменить текущий сценарий\n"
        "\n"
        "Просто напиши свой вопрос — я обработаю его через ИИ-агента."
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current is None:
        await message.answer("Нечего отменять.")
        return
    await state.clear()
    await message.answer("Сценарий отменён.")


# Команда /clear больше не нужна, так как история управляется агентом.
# Оставляем только информативное сообщение.
@router.message(Command("clear"))
async def cmd_clear(message: Message) -> None:
    await message.answer(
        "Очистка истории выполняется автоматически на стороне агента.\n"
        "Если нужно сбросить диалог, используйте /start или начните новый вопрос."
    )