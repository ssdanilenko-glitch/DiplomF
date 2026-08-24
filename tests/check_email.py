import asyncio
from app.services.email_service import email_service

async def main():
    print("Отправка тестового письма...")
    success = await email_service.send_message(
        subject="Тест интеграции DiplomF",
        body="Это тестовое сообщение из Python-скрипта.",
        recipient="danilenko@ukbmz.ru"
    )
    if success:
        print("Письмо успешно отправлено!")
    else:
        print("Ошибка при отправке. Проверьте логи и настройки пароля приложения Яндекса.")

if __name__ == "__main__":
    asyncio.run(main())