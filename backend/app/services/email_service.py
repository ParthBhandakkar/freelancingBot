import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def render_template(template_body: str, template_subject: str, variables: dict) -> tuple[str, str]:
    body = template_body
    subject = template_subject
    for key, value in variables.items():
        placeholder = "{{" + key + "}}"
        body = body.replace(placeholder, str(value))
        subject = subject.replace(placeholder, str(value))
    return subject, body


def get_smtp_config() -> dict:
    return {
        "host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "username": os.getenv("SMTP_USERNAME", ""),
        "password": os.getenv("SMTP_PASSWORD", ""),
        "from_email": os.getenv("SMTP_FROM_EMAIL", os.getenv("SMTP_USERNAME", "")),
        "from_name": os.getenv("SMTP_FROM_NAME", ""),
    }


async def send_email(
    to_email: str,
    subject: str,
    body: str,
    html_body: str = "",
) -> dict:
    config = get_smtp_config()
    if not config["username"] or not config["password"]:
        return {"success": False, "error": "SMTP not configured. Set SMTP_USERNAME and SMTP_PASSWORD in .env"}

    msg = MIMEMultipart("alternative")
    msg["From"] = f"{config['from_name']} <{config['from_email']}>" if config["from_name"] else config["from_email"]
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))
    if html_body:
        msg.attach(MIMEText(html_body, "html"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(config["host"], config["port"]) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(config["username"], config["password"])
            server.send_message(msg)
        return {"success": True, "to": to_email, "subject": subject}
    except Exception as e:
        return {"success": False, "error": str(e)}
