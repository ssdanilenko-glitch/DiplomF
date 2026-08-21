import httpx
from typing import Optional, Dict, Any

from express_bot.config import get_bot_settings

settings = get_bot_settings()


class BackendClient:
    def __init__(self, http_client: httpx.AsyncClient):
        self.client = http_client
        self.base_url = settings.backend_url

    async def process_message(
        self,
        user_id: str,
        chat_id: str,
        text: str,
        platform: str = "express",
    ) -> Dict[str, Any]:
        """Отправляет сообщение в бэкенд (единый API /api/process)."""
        url = f"{self.base_url}/api/process"
        payload = {
            "user_id": user_id,
            "chat_id": chat_id,
            "text": text,
            "platform": platform,
        }
        response = await self.client.post(url, json=payload, timeout=settings.request_timeout)
        response.raise_for_status()
        return response.json()

    async def get_ticket_status(self, ticket_uid: str) -> Dict[str, Any]:
        """Запрашивает статус обращения в ITILIUM через бэкенд."""
        url = f"{self.base_url}/api/ticket/{ticket_uid}"
        response = await self.client.get(url, timeout=settings.request_timeout)
        response.raise_for_status()
        return response.json()

    async def health_check(self) -> bool:
        try:
            response = await self.client.get(f"{self.base_url}/health", timeout=2.0)
            return response.status_code == 200
        except Exception:
            return False

    async def resume_agent(self, thread_id: str, resume_value: bool) -> Dict[str, Any]:
        """Возобновляет выполнение агента после interrupt'а."""
        url = f"{self.base_url}/api/resume"
        payload = {
            "thread_id": thread_id,
            "resume_value": resume_value,
            "platform": "express",
        }
        response = await self.client.post(url, json=payload, timeout=settings.request_timeout)
        response.raise_for_status()
        return response.json()