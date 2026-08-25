import requests
import time

def test_send_email():
    url = "http://localhost:8000/api/process"
    payload = {
        "user_id": "test_user",
        "chat_id": "test_chat",
        "text": "Как создать документ поступление товаров и услуг и ответ отправь по адресу danilenko@ukbmz.ru",
        "platform": "telegram"
    }
    response = requests.post(url, json=payload, timeout=60)
    print("Статус:", response.status_code)
    data = response.json()
    print("Ответ:", data)

    if data.get("need_approval"):
        thread_id = data.get("thread_id")
        print(f"⏳ Требуется подтверждение. thread_id: {thread_id}")
        # Автоматически подтверждаем (для теста)
        resume_payload = {
            "thread_id": thread_id,
            "resume_value": True,
            "platform": "telegram"
        }
        resume_response = requests.post("http://localhost:8000/api/resume", json=resume_payload, timeout=60)
        print("Результат подтверждения:", resume_response.json())
    else:
        print("HIL не сработал (возможно, проблема с function calling).")

if __name__ == "__main__":
    test_send_email()