import subprocess
import socket


def check_current_dns():
    """Проверка текущих DNS серверов"""

    # Проверка через resolv.conf (Linux)
    try:
        with open('/etc/resolv.conf', 'r') as f:
            print("Текущие DNS серверы:")
            for line in f:
                if line.startswith('nameserver'):
                    print(f"  {line.strip()}")
    except FileNotFoundError:
        print("Файл /etc/resolv.conf не найден (возможно Windows)")

    # Проверка разрешения домена
    try:
        ip = socket.gethostbyname('api.telegram.org')
        print(f"api.telegram.org разрешается в: {ip}")
    except Exception as e:
        print(f"Ошибка разрешения домена: {e}")


# Запуск проверки
check_current_dns()