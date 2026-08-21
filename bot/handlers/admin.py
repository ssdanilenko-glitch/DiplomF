"""Админ-команды бота отключены в новой архитектуре."""

import logging
from aiogram import Router
from aiogram.filters import Command, CommandObject, Filter
from aiogram.types import Message

log = logging.getLogger(__name__)


class IsAdmin(Filter):
    async def __call__(self, message: Message) -> bool:
        # Временно отключаем админ-команды
        return False


router = Router(name="admin")
router.message.filter(IsAdmin())


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    await message.answer("Административные функции временно недоступны.")


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message) -> None:
    await message.answer("Административные функции временно недоступны.")