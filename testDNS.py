import subprocess
import socket
import time


def check_windows_dns():
    """Проверка DNS настроек на Windows"""

    print("=== Текущие DNS настройки Windows ===\n")

    # Получение информации через ipconfig
    result = subprocess.run(['ipconfig', '/all'], capture_output=True, text=True, encoding='cp866')

    # Поиск DNS серверов в выводе
    for line in result.stdout.split('\n'):
        if 'DNS-серверы' in line or 'DNS Servers' in line:
            print(line.strip())

    # Проверка разрешения домена
    print(f"\nРазрешение api.telegram.org:")
    try:
        ip = socket.gethostbyname('api.telegram.org')
        print(f"  ✓ IP: {ip}")

        # Обратное разрешение
        hostname = socket.gethostbyaddr(ip)
        print(f"  ✓ Hostname: {hostname[0]}")
    except Exception as e:
        print(f"  ✗ Ошибка: {e}")


check_windows_dns()