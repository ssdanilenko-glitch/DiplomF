import asyncio
import aiohttp


async def check_proxy():
    proxy_url = "http://local_user:p32kcF26NhWE@72.56.89.38:8888"

    print("🔍 Проверка прокси-сервера...")
    print(f"Адрес: {proxy_url}")

    try:
        # Тест 1: Простое подключение к прокси
        print("\n1. Проверка подключения к прокси...")
        connector = aiohttp.TCPConnector()
        async with aiohttp.ClientSession(connector=connector) as session:
            # Попробуем подключиться к прокси без SSL проверки
            try:
                async with session.get(
                        'http://example.com',
                        proxy=proxy_url,
                        timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    print(f"   ✅ Прокси работает! Статус: {resp.status}")
            except Exception as e:
                print(f"   ❌ Ошибка подключения к прокси: {e}")

    except Exception as e:
        print(f"   ❌ Критическая ошибка: {e}")

    try:
        # Тест 2: Проверка пинга до прокси-сервера
        print("\n2. Проверка доступности хоста прокси...")
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(('72.56.89.38', 8888))
        sock.close()

        if result == 0:
            print("   ✅ Порт 8888 на 72.56.89.38 открыт")
        else:
            print(f"   ❌ Порт 8888 закрыт (код ошибки: {result})")

    except Exception as e:
        print(f"   ❌ Ошибка проверки порта: {e}")


if __name__ == "__main__":
    asyncio.run(check_proxy())