"""Обработчики медиа: фото, голос, аудио, документы (PDF/DOCX).

При переходе на единый агент (/api/process) медиафайлы не передаются,
поэтому бот просто отправляет текстовый запрос с упоминанием файла.
"""

import logging

from aiogram import F, Router
from aiogram.types import Message

from bot.services.backend_client import BackendClient
from bot.services.error_handling import handle_backend_error
from bot.handlers.text import pending_approvals
from bot.keyboards.inline import approval_kb

router = Router(name="media")
log = logging.getLogger(__name__)

MAX_PHOTO_BYTES = 2 * 1024 * 1024  # 2 МБ
MAX_DOC_BYTES = 10 * 1024 * 1024   # 10 МБ
ALLOWED_DOC_EXT = (".pdf", ".docx")


def _pick_photo_size(photos):
    """Выбирает самый большой размер фото, что меньше MAX_PHOTO_BYTES."""
    sorted_photos = sorted(photos, key=lambda p: p.file_size or 0, reverse=True)
    for p in sorted_photos:
        if (p.file_size or 0) <= MAX_PHOTO_BYTES:
            return p
    return sorted_photos[-1]  # самый маленький, если все больше лимита


async def _send_media_request(
    message: Message,
    backend: BackendClient,
    content: str,
    filename: str,
) -> None:
    """Отправляет запрос агенту с упоминанием файла."""
    try:
        result = await backend.process_message(
            user_id=str(message.chat.id),
            chat_id=str(message.chat.id),
            text=content,
            platform="telegram",
        )

        answer = result.get("answer", "")

        # Проверяем, требуется ли подтверждение
        if result.get("need_approval"):
            thread_id = result.get("thread_id")
            if thread_id:
                pending_approvals[str(message.chat.id)] = thread_id
                await message.answer(answer, reply_markup=approval_kb())
                return

        # Если нет подтверждения — просто отправляем ответ
        await message.answer(answer)

        # Отправляем вложения, если есть
        for attachment in result.get("attachments", []):
            await message.answer(attachment)

    except Exception as exc:
        await handle_backend_error(message, exc)


@router.message(F.photo)
async def on_photo(message: Message, backend: BackendClient) -> None:
    photo = _pick_photo_size(message.photo)
    # Мы не скачиваем фото, а просто сообщаем агенту о его наличии.
    caption = message.caption or "Пользователь прислал изображение"
    content = f"{caption} [приложено фото]"
    await _send_media_request(message, backend, content, "photo.jpg")


@router.message(F.voice)
async def on_voice(message: Message, backend: BackendClient) -> None:
    content = message.caption or "Пользователь прислал голосовое сообщение"
    content = f"{content} [приложен голосовой файл]"
    await _send_media_request(message, backend, content, "voice.ogg")


@router.message(F.audio)
async def on_audio(message: Message, backend: BackendClient) -> None:
    fname = message.audio.file_name or "audio.mp3"
    caption = message.caption or "Пользователь прислал аудиофайл"
    content = f"{caption} [приложен аудиофайл: {fname}]"
    await _send_media_request(message, backend, content, fname)


@router.message(F.document)
async def on_document(message: Message, backend: BackendClient) -> None:
    doc = message.document
    fname = (doc.file_name or "").lower()
    if not fname.endswith(ALLOWED_DOC_EXT):
        await message.answer(
            f"Поддерживаются только {', '.join(ALLOWED_DOC_EXT)}."
        )
        return
    if (doc.file_size or 0) > MAX_DOC_BYTES:
        await message.answer(
            f"Файл слишком большой (>{MAX_DOC_BYTES // 1024 // 1024} МБ)."
        )
        return
    caption = message.caption or "Пользователь прислал документ"
    content = f"{caption} [приложен документ: {doc.file_name}]"
    await _send_media_request(message, backend, content, doc.file_name or "document.bin")