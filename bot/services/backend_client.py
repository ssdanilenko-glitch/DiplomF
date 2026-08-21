"""Клиент к единому API агента (/api/process)."""

import json
from typing import Any, Optional
from uuid import UUID

import httpx


class BackendClient:
    def __init__(
        self,
        http: httpx.AsyncClient,
        admin_token: str = "",
        user_role: str = "write-with-approve",  # по умолчанию с подтверждением
    ) -> None:
        self.http = http
        self._admin_token = admin_token
        self.user_role = user_role

    # ---------- НОВЫЙ МЕТОД для агента ----------
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
        # Добавляем user_role в заголовки или в тело? Можно в configurable.
        headers = {"X-User-Role": self.user_role}
        r = await self.http.post(
            "/api/process",
            json=payload,
            headers=headers,
            timeout=120.0,
        )
        r.raise_for_status()
        return r.json()

    # ---------- Методы для подтверждений (resume) ----------
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
            "/api/resume",  # нужно добавить такой эндпоинт на бэкенде
            json=payload,
            timeout=60.0,
        )
        r.raise_for_status()
        return r.json()

    # ---------- Остальные методы (для обратной совместимости) ----------
    async def get_or_create_chat(
        self,
        owner_external_id: str,
        interface: str,
    ) -> UUID:
        """Оставлен для совместимости с /clear и feedback."""
        r = await self.http.post(
            "/chats",
            json={
                "owner_external_id": owner_external_id,
                "interface": interface,
            },
            headers={"X-Owner-External-Id": owner_external_id},
        )
        r.raise_for_status()
        return UUID(r.json()["chat_id"])

    async def clear_messages(
        self,
        chat_id: UUID,
        owner_external_id: str | None = None,
    ) -> None:
        headers = (
            {"X-Owner-External-Id": owner_external_id}
            if owner_external_id
            else {}
        )
        r = await self.http.delete(
            f"/chats/{chat_id}/messages", headers=headers
        )
        r.raise_for_status()

    async def post_feedback(
        self,
        chat_id: UUID,
        message_id: str,
        owner_external_id: str,
        value: str,
    ) -> None:
        r = await self.http.post(
            f"/chats/{chat_id}/messages/{message_id}/feedback",
            json={"owner_external_id": owner_external_id, "value": value},
            headers={"X-Owner-External-Id": owner_external_id},
        )
        r.raise_for_status()

    # ---------- Админские методы (без изменений) ----------
    def _admin_headers(self) -> dict[str, str]:
        return {"X-Admin-Token": self._admin_token}

    async def get_admin_stats(self, window_hours: int = 24) -> dict:
        r = await self.http.get(
            "/chats/admin/stats",
            params={"window_hours": window_hours},
            headers=self._admin_headers(),
        )
        r.raise_for_status()
        return r.json()

    async def broadcast(self, text: str, interface: str = "telegram") -> dict:
        r = await self.http.post(
            "/chats/admin/broadcast",
            json={"text": text, "interface": interface},
            headers=self._admin_headers(),
        )
        r.raise_for_status()
        return r.json()

    async def set_handoff_status(
        self,
        owner_external_id: str,
        status: str,
        interface: str = "telegram",
    ) -> dict:
        r = await self.http.post(
            "/chats/admin/handoff",
            json={
                "owner_external_id": owner_external_id,
                "interface": interface,
                "status": status,
            },
            headers=self._admin_headers(),
        )
        r.raise_for_status()
        return r.json()

    async def fetch_pending_alerts(self) -> list[dict]:
        r = await self.http.get(
            "/chats/admin/alerts", headers=self._admin_headers()
        )
        r.raise_for_status()
        return r.json()

    async def ack_alert(self, alert_id: int) -> None:
        r = await self.http.post(
            f"/chats/admin/alerts/{alert_id}/ack",
            headers=self._admin_headers(),
        )
        r.raise_for_status()

    async def aclose(self) -> None:
        await self.http.aclose()