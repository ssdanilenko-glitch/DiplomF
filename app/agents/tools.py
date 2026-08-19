"""Инструменты агента.

`multiply` — простой самодостаточный инструмент. `search_knowledge_base` — RAG
как инструмент: обёртка над корпоративной базой знаний. Поиск инжектируется
как async-callable, чтобы инструмент не зависел от инициализации RAG-сервиса
напрямую и легко подменялся в тестах.
"""

from collections.abc import Awaitable, Callable

from langchain_core.tools import BaseTool, tool
from app.services.itilium_client import ItiliumClient


@tool
def multiply(a: int, b: int) -> int:
    """Перемножает два целых числа. Вызывать для любого умножения."""
    return a * b


def build_search_knowledge_base(
    search_fn: Callable[[str], Awaitable[dict]],
) -> BaseTool:
    """Собирает инструмент поиска по базе знаний поверх переданного `search_fn`.

    `search_fn(query)` возвращает контракт RAG-сервиса
    `{answer, sources[id, file_name, ...], confident, ...}`.
    """

    @tool
    async def search_knowledge_base(query: str) -> str:
        """Ищет ответ в корпоративной базе знаний по текстовому запросу.

        Вызывать, когда нужен факт из документов компании. Не вызывать для
        арифметики или общих знаний, которые модель знает сама.
        """
        result = await search_fn(query)
        answer = result.get("answer", "")
        sources = result.get("sources", [])
        if not sources:
            return answer
        cited = "; ".join(
            f"[{s.get('id')}] {s.get('file_name', '')}".strip() for s in sources
        )
        return f"{answer}\nИсточники: {cited}"

    return search_knowledge_base

def build_create_ticket_tool(
    itilium_client: ItiliumClient | None,
) -> BaseTool:
    """Создаёт инструмент для создания обращения в 1С:ITILIUM.

    Принимает клиент ITILIUM (инъекция зависимости). Если клиент None —
    инструмент возвращает ошибку.
    """

    @tool
    async def create_itilium_ticket(
        topic: str,
        description: str,
        service_uid: str | None = None,
        category_uid: str | None = None,
    ) -> str:
        """
        Создаёт обращение в 1С:ITILIUM.

        Вызывай этот инструмент, если:
        - не нашёл ответ в базе знаний;
        - пользователь сообщает о проблеме, которую невозможно решить автоматически;
        - требуется вмешательство службы поддержки.

        Аргументы:
            topic: краткая тема обращения (например: "Не работает отчёт по бюджету")
            description: подробное описание проблемы, можно включить контекст
            service_uid: (опционально) UID услуги в ITILIUM, если известен
            category_uid: (опционально) UID категории в ITILIUM, если известна

        Возвращает: сообщение о результате создания обращения.
        """
        if itilium_client is None:
            return "❌ Клиент 1С:ITILIUM недоступен. Обращение не создано."

        try:
            ticket = await itilium_client.add_new_incident(
                topic=topic,
                description=description,
                service_uid=service_uid,
                category_uid=category_uid,
            )
            ticket_uid = ticket.get("UID")
            return f"✅ Обращение #{ticket_uid} успешно создано в 1С:ITILIUM."
        except Exception as e:
            return f"❌ Не удалось создать обращение: {e}"

    return create_itilium_ticket

