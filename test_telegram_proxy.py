import asyncio
import os
import httpx

# Конфигурация
TELEGRAM_TOKEN = "8763077202:AAGhvgxN8aWYXVM49zPOAXTN5SNQ7vv9y9s"
API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe"

# Настройки прокси из вашего оригинального файла
PROXY_HTTP = "http://local_user:p32kcF26NhWE@72.56.89.38:8888"
PROXY_SOCKS5 = "socks5://local_user:p32kcF26NhWE@72.56.89.38:1081"


async def check_proxy(proxy_url: str, proxy_type: str) -> None:
    """Проверяет доступность Telegram API через указанный прокси."""
    print(f"\n🔍 Проверка {proxy_type} прокси: {proxy_url.split('@')[-1]}")

    try:
        async with httpx.AsyncClient(proxy=proxy_url, timeout=15.0) as client:
            response = await client.get(API_URL)

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    bot_name = data["result"].get("username", "N/A")
                    print(f"   ✅ УСПЕХ! Бот: @{bot_name}")
                else:
                    print(f"   ❌ Ошибка API: {data.get('description')}")
            else:
                print(f"   ❌ HTTP {response.status_code}: {response.text[:100]}")

    except httpx.ProxyError as e:
        print(f"   ❌ Ошибка прокси: {e}")
    except httpx.ConnectTimeout:
        print(f"   ❌ Таймаут соединения (прокси не отвечает)")
    except Exception as e:
        print(f"   ❌ Неизвестная ошибка: {type(e).__name__}: {e}")


async def main():
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ ДОСТУПА К TELEGRAM BOT API ЧЕРЕЗ ПРОКСИ")
    print("=" * 60)

    # Тест 1: Прямое подключение (без прокси) для сравнения
    print("\n🔍 Проверка прямого подключения (без прокси)...")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(API_URL)
            print(f"   ✅ Прямой доступ: HTTP {r.status_code}")
    except Exception as e:
        print(f"   ⚠️  Прямой доступ недоступен: {type(e).__name__}")

    # Тест 2: HTTP прокси
    await check_proxy(PROXY_HTTP, "HTTP")

    # Тест 3: SOCKS5 прокси
    # Требуется: pip install httpx[socks]
    await check_proxy(PROXY_SOCKS5, "SOCKS5")

    print("\n" + "=" * 60)
    print("Тестирование завершено.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())