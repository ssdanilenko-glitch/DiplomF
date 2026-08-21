"""Команда /operator отключена в новой архитектуре."""

import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

log = logging.getLogger(__name__)
router = Router(name="handoff")


@router.message(Command("operator"))
async def cmd_operator(message: Message) -> None:
    await message.answer("Переключение на оператора временно недоступно.")