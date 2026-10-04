"""SMTP STARTTLS brief sender; dry-run is the default."""
from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from radar.deliver.settings import settings


def send(subject: str, text: str, html: str | None = None, dry_run: bool = True) -> None:
    if dry_run:
        print(f"[Email dry-run]\nSubject: {subject}\n{text}")
        if html is not None:
            print(f"HTML alternative:\n{html}")
        return
    values = settings(("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "EMAIL_FROM", "EMAIL_TO"))
    recipients = [recipient.strip() for recipient in values["EMAIL_TO"].split(",") if recipient.strip()]
    if not values["SMTP_HOST"] or not values["EMAIL_FROM"] or not recipients:
        print("Email skipped: channel settings are empty.")
        return
    if bool(values["SMTP_USER"]) != bool(values["SMTP_PASSWORD"]):
        print("Email skipped: SMTP authentication settings are incomplete.")
        return
    try:
        port = int(values["SMTP_PORT"] or "587")
    except ValueError:
        raise RuntimeError("SMTP_PORT must be an integer.") from None
    message = EmailMessage()
    message["Subject"], message["From"], message["To"] = subject, values["EMAIL_FROM"], ", ".join(recipients)
    message.set_content(text)
    if html is not None:
        message.add_alternative(html, subtype="html")
    try:
        with smtplib.SMTP(values["SMTP_HOST"], port, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
            if values["SMTP_USER"]:
                smtp.login(values["SMTP_USER"], values["SMTP_PASSWORD"])
            smtp.send_message(message, from_addr=values["EMAIL_FROM"], to_addrs=recipients)
    except (smtplib.SMTPException, OSError):
        raise RuntimeError("Email delivery failed; check connection and channel settings.") from None
    print("Email brief delivered.")
