import asyncio
import time
from app.services.itilium_client import ItiliumClient


async def main():
    client = ItiliumClient()

    print("=== Тест 1: Аутентификация ===")
    t0 = time.monotonic()
    result = await client.authenticate()
    print(f"Результат: {result}, Время: {time.monotonic() - t0:.2f}s\n")

    print("=== Тест 2: Список услуг ===")
    t0 = time.monotonic()
    services = await client.get_list_services()
    print(f"Получено услуг: {len(services)}, Время: {time.monotonic() - t0:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())