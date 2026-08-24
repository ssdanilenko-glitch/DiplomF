import httpx
from typing import Optional, Dict, Any, List
from app.core.config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()


class ItiliumClient:
    def __init__(self):
        self.base_url = settings.ITILIUM_BASE_URL
        # Явное преобразование SecretStr в str для избежания TypeError
        self.username = str(settings.ITILIUM_USERNAME)
        self.password = str(settings.ITILIUM_PASSWORD)

        # Флаг отключения сервиса (по умолчанию True, если не указано иное)
        self.enabled = getattr(settings, 'ITILIUM_ENABLED', True)
        if not self.enabled:
            logger.warning("Сервис ITILIUM ОТКЛЮЧЕН через настройки конфигурации.")

    async def _request(
            self,
            method: str,
            endpoint: str,
            data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Базовый метод для выполнения запросов к API 1С:ITILIUM."""

        # Если сервис отключен, возвращаем заглушку мгновенно
        if not self.enabled:
            logger.info(f"[MOCK] Запрос пропущен: {method} {endpoint}")
            return {"mock": True, "status": "disabled"}

        url = f"{self.base_url}{endpoint}"
        auth = (self.username, self.password)

        try:
            async with httpx.AsyncClient(auth=auth, timeout=30.0) as client:
                if method.upper() == "GET":
                    response = await client.get(url)
                elif method.upper() == "POST":
                    response = await client.post(url, json=data)
                else:
                    raise ValueError(f"Unsupported method: {method}")

                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Ошибка запроса к ITILIUM: {e}")
            raise

    # --- Основные методы API (остаются без изменений) ---

    async def authenticate(self) -> bool:
        try:
            result = await self._request("GET", "/authenticate")
            # При отключении считаем аутентификацию успешной
            return result.get("mock", False) or True
        except Exception:
            return False

    async def add_new_incident(
            self,
            topic: str,
            description: str,
            service_uid: Optional[str] = None,
            category_uid: Optional[str] = None,
            configuration_items: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        payload = {
            "Topic": topic,
            "Data": "",
            "Description": description,
        }
        if service_uid:
            payload["MembershipServices"] = {"UID": service_uid}
        if category_uid:
            payload["Category"] = {"UID": category_uid}
        if configuration_items:
            payload["ConfigurationItems"] = [{"UID": uid} for uid in configuration_items]

        return await self._request("POST", "/addNewIncident", data=payload)

    async def get_incident_detail(self, incident_uid: str) -> Dict[str, Any]:
        return await self._request("GET", f"/getDetailInfoIncindent/{incident_uid}")

    async def get_list_services(self) -> Dict[str, Any]:
        return await self._request("GET", "/getListServices")

    async def get_list_categories(self) -> Dict[str, Any]:
        return await self._request("GET", "/getListCategories")

    async def add_comment_to_incident(self, incident_uid: str, comment: str) -> Dict[str, Any]:
        payload = {"UID": incident_uid, "Comment": comment}
        return await self._request("POST", "/addCommentToIncident", data=payload)