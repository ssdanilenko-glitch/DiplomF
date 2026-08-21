import asyncio
import httpx

url = "https://api.ipify.org?format=json"

async def main():
    # HTTP прокси (порт 8888)
    try:
        async with httpx.AsyncClient(
            proxy="http://local_user:p32kcF26NhWE@72.56.89.38:8888",
            timeout=10.0
        ) as http:
            r = await http.get(url)
            print("HTTP  8888:", r.status_code, r.text)
    except Exception as e:
        print("HTTP  8888: ошибка –", e)

    # SOCKS5 прокси (порт 1081)
    try:
        # Для socks5 нужен пакет socksio: pip install httpx[socks]
        async with httpx.AsyncClient(
            proxy="socks5://local_user:p32kcF26NhWE@72.56.89.38:1081",
            timeout=10.0
        ) as socks:
            r = await socks.get(url)
            print("SOCKS5 1081:", r.status_code, r.text)
    except Exception as e:
        print("SOCKS5 1081: ошибка –", e)

if __name__ == "__main__":
    asyncio.run(main())