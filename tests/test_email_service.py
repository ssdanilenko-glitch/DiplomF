import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from email.mime.multipart import MIMEMultipart

from app.services.email_service import EmailService, settings


@pytest.fixture
def email_service():
    """Фикстура для создания экземпляра сервиса с тестовыми настройками."""
    # Подменяем настройки на тестовые (чтобы не зависеть от .env)
    with patch.object(settings, "yandex_email", "test@yandex.ru"), \
         patch.object(settings, "yandex_app_password", "testpass"), \
         patch.object(settings, "exchange_recipient_email", "recipient@example.com"):
        service = EmailService()
        # Явно переопределяем атрибуты, чтобы они совпали с моками
        service.sender_email = "test@yandex.ru"
        service.sender_password = "testpass"
        service.recipient_email = "recipient@example.com"
        yield service

@pytest.mark.asyncio
async def test_send_message_success(email_service):
    """Проверяет успешную отправку письма."""
    with patch("app.services.email_service.aiosmtplib.SMTP") as MockSMTP:
        # Настраиваем мок SMTP-клиента
        mock_smtp = AsyncMock()
        mock_smtp.__aenter__ = AsyncMock(return_value=mock_smtp)
        mock_smtp.__aexit__ = AsyncMock(return_value=None)
        mock_smtp.login = AsyncMock()
        mock_smtp.send_message = AsyncMock()
        MockSMTP.return_value = mock_smtp

        # Вызываем метод
        result = await email_service.send_message(
            subject="Test Subject",
            body="Test Body",
            recipient="user@example.com"
        )

        # Проверяем, что SMTP-клиент был создан с правильными параметрами
        MockSMTP.assert_called_once_with(
            hostname=email_service.smtp_host,
            port=email_service.smtp_port,
            use_tls=email_service.use_tls
        )
        # Проверяем логин и отправку
        mock_smtp.login.assert_awaited_once_with("test@yandex.ru", "testpass")
        mock_smtp.send_message.assert_awaited_once()

        # Проверяем, что сообщение имеет правильные заголовки
        sent_msg = mock_smtp.send_message.call_args[0][0]
        assert sent_msg["From"] == "test@yandex.ru"
        assert sent_msg["To"] == "user@example.com"
        assert sent_msg["Subject"] == "Test Subject"

        # Убеждаемся, что результат True
        assert result is True


@pytest.mark.asyncio
async def test_send_message_with_default_recipient(email_service):
    """Проверяет, что при отсутствии получателя используется значение по умолчанию."""
    with patch("app.services.email_service.aiosmtplib.SMTP") as MockSMTP:
        mock_smtp = AsyncMock()
        mock_smtp.__aenter__ = AsyncMock(return_value=mock_smtp)
        mock_smtp.__aexit__ = AsyncMock(return_value=None)
        mock_smtp.login = AsyncMock()
        mock_smtp.send_message = AsyncMock()
        MockSMTP.return_value = mock_smtp

        # Не передаём recipient
        result = await email_service.send_message(
            subject="Test",
            body="Body"
        )

        # Проверяем, что получатель взят из настроек
        sent_msg = mock_smtp.send_message.call_args[0][0]
        assert sent_msg["To"] == email_service.recipient_email
        assert result is True


@pytest.mark.asyncio
async def test_send_message_html(email_service):
    """Проверяет, что письмо формируется как HTML, если указан флаг."""
    with patch("app.services.email_service.aiosmtplib.SMTP") as MockSMTP:
        mock_smtp = AsyncMock()
        mock_smtp.__aenter__ = AsyncMock(return_value=mock_smtp)
        mock_smtp.__aexit__ = AsyncMock(return_value=None)
        mock_smtp.login = AsyncMock()
        mock_smtp.send_message = AsyncMock()
        MockSMTP.return_value = mock_smtp

        await email_service.send_message(
            subject="HTML Test",
            body="<h1>Hello</h1>",
            is_html=True
        )

        sent_msg = mock_smtp.send_message.call_args[0][0]
        # Проверяем, что содержимое закодировано как HTML
        # Текст внутри MIMEText должен иметь subtype 'html'
        parts = sent_msg.get_payload()
        assert len(parts) == 1
        part = parts[0]
        assert part.get_content_type() == "text/html"
        assert part.get_payload() == "<h1>Hello</h1>"


@pytest.mark.asyncio
async def test_send_message_auth_error(email_service):
    """Проверяет обработку ошибки аутентификации (SMTPAuthenticationError)."""
    from aiosmtplib.errors import SMTPAuthenticationError

    with patch("app.services.email_service.aiosmtplib.SMTP") as MockSMTP:
        mock_smtp = AsyncMock()
        mock_smtp.__aenter__ = AsyncMock(return_value=mock_smtp)
        mock_smtp.__aexit__ = AsyncMock(return_value=None)
        mock_smtp.login = AsyncMock(side_effect=SMTPAuthenticationError(535, b"Authentication failed"))
        MockSMTP.return_value = mock_smtp

        result = await email_service.send_message(
            subject="Auth Test",
            body="Test"
        )

        # Должен вернуть False
        assert result is False
        # Проверяем, что login был вызван
        mock_smtp.login.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_message_generic_error(email_service):
    """Проверяет обработку любых других исключений."""
    with patch("app.services.email_service.aiosmtplib.SMTP") as MockSMTP:
        mock_smtp = AsyncMock()
        mock_smtp.__aenter__ = AsyncMock(return_value=mock_smtp)
        mock_smtp.__aexit__ = AsyncMock(return_value=None)
        mock_smtp.login = AsyncMock(side_effect=TimeoutError("Connection timeout"))
        MockSMTP.return_value = mock_smtp

        result = await email_service.send_message(
            subject="Error Test",
            body="Test"
        )

        assert result is False
        mock_smtp.login.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_message_without_subject_and_body(email_service):
    """Проверяет поведение, если тема и тело пустые (должны отправить пустые строки)."""
    with patch("app.services.email_service.aiosmtplib.SMTP") as MockSMTP:
        mock_smtp = AsyncMock()
        mock_smtp.__aenter__ = AsyncMock(return_value=mock_smtp)
        mock_smtp.__aexit__ = AsyncMock(return_value=None)
        mock_smtp.login = AsyncMock()
        mock_smtp.send_message = AsyncMock()
        MockSMTP.return_value = mock_smtp

        result = await email_service.send_message(
            subject="",
            body=""
        )

        assert result is True
        sent_msg = mock_smtp.send_message.call_args[0][0]
        assert sent_msg["Subject"] == ""
        # Тело должно быть пустым
        parts = sent_msg.get_payload()
        assert len(parts) == 1
        part = parts[0]
        assert part.get_payload() == ""