"""Клиент к единому API агента (/api/process)."""

import httpx


class BackendClient:
    def __init__(
        self,
        http: httpx.AsyncClient,
        user_role: str = "write-with-approve",
    ) -> None:
        self.http = http
        self.user_role = user_role

    async def process_message(
        self,
        user_id: str,
        chat_id: str,
        text: str,
        platform: str = "telegram",
    ) -> dict:
        """
        Отправляет сообщение агенту через /api/process.
        Возвращает словарь с полями:
            answer, attachments, action, context, ticket_uid, need_approval
        """
        payload = {
            "user_id": user_id,
            "chat_id": chat_id,
            "text": text,
            "platform": platform,
        }
        # user_role можно передать в configurable (если бэкенд поддерживает)
        headers = {"X-User-Role": self.user_role}
        r = await self.http.post(
            "/api/process",
            json=payload,
            headers=headers,
            timeout=180.0,
        )
        r.raise_for_status()
        return r.json()

    async def resume_agent(
        self,
        thread_id: str,
        resume_value: bool,
        platform: str = "telegram",
    ) -> dict:
        """
        Отправляет подтверждение (resume) для продолжения прерванного агента.
        """
        payload = {
            "thread_id": thread_id,
            "resume_value": resume_value,
            "platform": platform,
        }
        r = await self.http.post(
            "/api/resume",
            json=payload,
            timeout=60.0,
        )
        r.raise_for_status()
        return r.json()

    async def aclose(self) -> None:
        await self.http.aclose()