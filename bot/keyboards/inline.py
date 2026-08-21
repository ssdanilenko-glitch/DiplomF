# bot/keyboards/inline.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Константы для callback_data
FEEDBACK_CB_PREFIX = "fb"
FEEDBACK_UP = "up"
FEEDBACK_DOWN = "down"
FEEDBACK_VALUES = (FEEDBACK_UP, FEEDBACK_DOWN)

# Список тем для /ask (можно дополнить)
TOPICS = [
    ("1С:ERP", "1c_erp"),
    ("Бюджетирование", "budget"),
    ("Закупки", "purchase"),
    ("Склады", "warehouse"),
    ("Техподдержка", "support"),
    ("Документооборот", "docflow"),
    ("Отчетность", "reporting"),
    ("Другое", "other"),
]

def topics_kb() -> InlineKeyboardMarkup:
    """Клавиатура для выбора темы в FSM-сценарии /ask."""
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=f"topic:{slug}")]
        for label, slug in TOPICS
    ]
    buttons.append([InlineKeyboardButton(text="❌ Отменить", callback_data="topic:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def feedback_kb(message_id: str) -> InlineKeyboardMarkup:
    """Клавиатура для оценки полезности ответа."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="👍 Полезно",
                callback_data=f"{FEEDBACK_CB_PREFIX}:{FEEDBACK_UP}:{message_id}"
            ),
            InlineKeyboardButton(
                text="👎 Не полезно",
                callback_data=f"{FEEDBACK_CB_PREFIX}:{FEEDBACK_DOWN}:{message_id}"
            ),
        ]
    ])

def approval_kb() -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения опасного действия."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data="approve_yes"),
            InlineKeyboardButton(text="❌ Нет", callback_data="approve_no"),
        ]
    ])