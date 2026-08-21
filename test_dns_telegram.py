import asyncio
import aiohttp
import ssl


async def test_proxy_connection():
    """Тестирование подключения через прокси"""

    proxy_url = "http://local_user:p32kcF26NhWE@72.56.89.38:8888"

    # Настройка SSL
    ssl_context = ssl.create_default_context()
    connector = aiohttp.TCPConnector(ssl=ssl_context)

    async with aiohttp.ClientSession(
            connector=connector,
            proxy=proxy_url,
    ) as session:
        try:
            # Тест 1: Проверка доступа к Telegram API
            print("🔍 Тест 1: Проверка доступа к api.telegram.org...")
            async with session.get('https://api.telegram.org/', timeout=10) as resp:
                print(f"   Статус: {resp.status}")
                if resp.status == 200:
                    print("   ✅ Доступ к Telegram API работает!")
                else:
                    print(f"   ⚠️ Неожиданный статус: {resp.status}")

            # Тест 2: Проверка разрешения DNS
            print("\n🔍 Тест 2: Проверка DNS...")
            async with session.get('https://api.telegram.org/bot<YOUR_TOKEN>/getMe', timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"   ✅ Бот: @{data['result']['username']}")
                elif resp.status == 401:
                    print("   ⚠️ Неверный токен (но соединение работает)")
                else:
                    print(f"   Статус: {resp.status}")

        except aiohttp.ClientProxyConnectionError as e:
            print(f"   ❌ Ошибка подключения к прокси: {e}")
        except aiohttp.ClientConnectorError as e:
            print(f"   ❌ Ошибка соединения: {e}")
        except asyncio.TimeoutError:
            print("   ❌ Таймаут соединения")
        except Exception as e:
            print(f"   ❌ Неизвестная ошибка: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 ТЕСТИРОВАНИЕ ПРОКСИ КОНФИГУРАЦИИ")
    print("=" * 60)
    asyncio.run(test_proxy_connection())