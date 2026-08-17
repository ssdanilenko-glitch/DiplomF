# app/services/itilium_client.py
import httpx
from typing import Optional, Dict, Any, List
from app.core.config import get_settings

settings = get_settings()

class ItiliumClient:
    def __init__(self):
        # Базовый URL опубликованного HTTP-сервиса 1С:ITILIUM
        self.base_url = settings.ITILIUM_BASE_URL
        # Учетные данные для аутентификации (базовая HTTP-авторизация)
        self.username = settings.ITILIUM_USERNAME
        self.password = settings.ITILIUM_PASSWORD

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Базовый метод для выполнения запросов к API 1С:ITILIUM."""
        url = f"{self.base_url}{endpoint}"
        auth = (self.username, self.password)

        async with httpx.AsyncClient(auth=auth, timeout=30.0) as client:
            if method.upper() == "GET":
                response = await client.get(url)
            elif method.upper() == "POST":
                response = await client.post(url, json=data)
            else:
                raise ValueError(f"Unsupported method: {method}")

            response.raise_for_status()
            return response.json()

    # --- Основные методы API ---

    async def authenticate(self) -> bool:
        """Проверка аутентификации (GET /authenticate)."""
        try:
            await self._request("GET", "/authenticate")
            return True
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
        """
        Создание нового инцидента (POST /addNewIncident).[reference:0]
        Поля: Topic (тема), Data (дата), Description (описание),
        MembershipServices.UID (состав услуги),
        Category.UID (категория),
        ConfigurationItems[].UID (конфигурационные единицы).
        """
        payload = {
            "Topic": topic,
            "Data": "",  # можно оставить пустым — подставится текущая дата
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
        """
        Получение детальной информации по обращению (GET /getDetailInfoIncindent/{idDoc}).[reference:1]
        """
        return await self._request("GET", f"/getDetailInfoIncindent/{incident_uid}")

    async def get_list_services(self) -> Dict[str, Any]:
        """Получение всех услуг/составов услуг (GET /getListServices).[reference:2]"""
        return await self._request("GET", "/getListServices")

    async def get_list_categories(self) -> Dict[str, Any]:
        """Получение всех категорий (GET /getListCategories).[reference:3]"""
        return await self._request("GET", "/getListCategories")

    async def add_comment_to_incident(self, incident_uid: str, comment: str) -> Dict[str, Any]:
        """Добавление комментария к инциденту (POST /addCommentToIncident).[reference:4]"""
        payload = {"UID": incident_uid, "Comment": comment}
        return await self._request("POST", "/addCommentToIncident", data=payload)