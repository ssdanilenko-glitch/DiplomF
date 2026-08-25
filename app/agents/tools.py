"""Все инструменты агента: фабрики и готовые экземпляры."""

from collections.abc import Awaitable, Callable
from langchain_core.tools import BaseTool, tool
from app.services.email_service import get_email_service
from app.services.itilium_client import ItiliumClient


# ---------- 1. Базовый инструмент ----------
@tool
def multiply(a: int, b: int) -> int:
    """Перемножает два целых числа."""
    return a * b


# ---------- 2. Инструмент поиска по базе знаний ----------
def build_search_knowledge_base(
    search_fn: Callable[[str], Awaitable[dict]],
) -> BaseTool:
    """Создаёт инструмент поиска по базе знаний."""

    @tool
    async def search_knowledge_base(query: str) -> str:
        """Ищет ответ в корпоративной базе знаний."""
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


# ---------- 3. Инструмент отправки почты (опасный) ----------
def build_send_email_tool() -> BaseTool:
    """Создаёт инструмент для отправки письма."""

    @tool
    async def send_email(to: str, subject: str, body: str) -> str:
        """Отправляет письмо на указанный адрес. Требует подтверждения."""
        email_service = get_email_service()
        success = await email_service.send_message(
            subject=subject,
            body=body,
            recipient=to,
            is_html=False
        )
        if success:
            return f"✅ Письмо успешно отправлено на {to}"
        else:
            return f"❌ Не удалось отправить письмо на {to}. Проверьте настройки SMTP."

    return send_email


# ---------- 4. Инструмент ITILIUM (опасный) ----------
def build_create_ticket_tool(
    itilium_client: ItiliumClient | None,
) -> BaseTool:
    """Создаёт инструмент для создания обращения в 1С:ITILIUM."""

    @tool
    async def create_itilium_ticket(
        topic: str,
        description: str,
        service_uid: str | None = None,
        category_uid: str | None = None,
    ) -> str:
        """Создаёт обращение в 1С:ITILIUM."""
        if itilium_client is None:
            return "❌ Клиент 1С:ITILIUM недоступен."
        try:
            ticket = await itilium_client.add_new_incident(
                topic=topic,
                description=description,
                service_uid=service_uid,
                category_uid=category_uid,
            )
            ticket_uid = ticket.get("UID")
            return f"✅ Обращение #{ticket_uid} успешно создано."
        except Exception as e:
            return f"❌ Не удалось создать обращение: {e}"

    return create_itilium_ticket


# ---------- 5. Фабрика для создания всех инструментов ----------
def build_all_tools(
    search_fn: Callable[[str], Awaitable[dict]],
    itilium_client: ItiliumClient | None,
) -> list[BaseTool]:
    """Создаёт и возвращает полный список инструментов для агента."""
    return [
        multiply,
        build_search_knowledge_base(search_fn),
        build_send_email_tool(),
        # УДАЛИТЕ ЭТУ СТРОКУ:
        # build_create_ticket_tool(itilium_client),
    ]