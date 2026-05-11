import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import urlencode


def send_email(to_email, subject, body, from_name="LocalOS"):
    """Send a plain-text transactional email through configured SMTP."""
    try:
        smtp_server = os.getenv("SMTP_SERVER", "mail.hosting.reg.ru")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_username = os.getenv("SMTP_USERNAME", "info@localos.pro")
        smtp_password = os.getenv("SMTP_PASSWORD")

        if not smtp_password:
            print("SMTP_PASSWORD is not configured")
            return False

        message = MIMEMultipart()
        message["From"] = f"{from_name} <{smtp_username}>"
        message["To"] = to_email
        message["Subject"] = subject
        message.attach(MIMEText(body, "plain", "utf-8"))

        server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.send_message(message)
        server.quit()

        print(f"Email sent to {to_email}")
        return True
    except Exception:
        print("Email delivery failed")
        return False


def build_email_verification_link(token):
    app_url = os.getenv("PUBLIC_APP_URL", "https://localos.pro").rstrip("/")
    return f"{app_url}/verify-email?token={token}"


def build_password_setup_link(email, token):
    app_url = os.getenv("PUBLIC_APP_URL", "https://localos.pro").rstrip("/")
    query = urlencode({"email": email, "token": token})
    return f"{app_url}/set-password?{query}"


def send_verification_email(email, name, token):
    link = build_email_verification_link(token)
    display_name = str(name or "").strip() or "пользователь"
    subject = "Подтвердите email в LocalOS"
    body = f"""
Здравствуйте, {display_name}!

Подтвердите email, чтобы завершить регистрацию в LocalOS:
{link}

Если вы не регистрировались в LocalOS, просто проигнорируйте это письмо.

---
LocalOS
    """
    return send_email(email, subject, body)


def send_password_setup_email(email, name, token):
    link = build_password_setup_link(email, token)
    display_name = str(name or "").strip() or "пользователь"
    subject = "Доступ в LocalOS: задайте пароль"
    body = f"""
Здравствуйте, {display_name}!

Для вашего аккаунта LocalOS открыт доступ. Задайте пароль по ссылке:
{link}

Ссылка одноразовая. Если вы не ожидали это письмо, просто проигнорируйте его.

---
LocalOS
    """
    return send_email(email, subject, body)
