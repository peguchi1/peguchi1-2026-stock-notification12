from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable

import requests
import smtplib
from email.message import EmailMessage


@dataclass
class NotificationMessage:
    title: str
    body: str


class Notifier:
    def __init__(self, slack_enabled: bool, pushover_enabled: bool, email_enabled: bool) -> None:
        self.slack_enabled = slack_enabled
        self.pushover_enabled = pushover_enabled
        self.email_enabled = email_enabled

    def notify(self, message: NotificationMessage) -> None:
        sent = False
        if self.slack_enabled:
            sent = self._send_slack(message) or sent
        if self.pushover_enabled:
            sent = self._send_pushover(message) or sent
        if self.email_enabled:
            sent = self._send_email(message) or sent
        if not sent:
            print(self._format_stdout(message))

    def notify_batch(self, title: str, lines: Iterable[str]) -> None:
        body = "\n".join(lines)
        self.notify(NotificationMessage(title=title, body=body))

    def _send_slack(self, message: NotificationMessage) -> bool:
        webhook = os.getenv("SLACK_WEBHOOK_URL")
        if not webhook:
            return False
        payload = {"text": f"*{message.title}*\n{message.body}"}
        response = requests.post(webhook, json=payload, timeout=20)
        return response.status_code < 300

    def _send_pushover(self, message: NotificationMessage) -> bool:
        user_key = os.getenv("PUSHOVER_USER_KEY")
        token = os.getenv("PUSHOVER_APP_TOKEN")
        if not user_key or not token:
            return False
        payload = {
            "token": token,
            "user": user_key,
            "title": message.title,
            "message": message.body,
        }
        response = requests.post("https://api.pushover.net/1/messages.json", data=payload, timeout=20)
        return response.status_code < 300

    def _send_email(self, message: NotificationMessage) -> bool:
        to_addr = os.getenv("MAIL_ADDRESS_NOTIFICATION_TO")
        host = os.getenv("SMTP_HOST")
        port = int(os.getenv("SMTP_PORT", "587"))
        user = os.getenv("SMTP_USER")
        password = os.getenv("SMTP_PASSWORD")
        from_addr = os.getenv("SMTP_FROM") or user
        tls_enabled = os.getenv("SMTP_TLS", "true").lower() in {"1", "true", "yes", "on"}

        if not to_addr or not host or not user or not password or not from_addr:
            return False

        msg = EmailMessage()
        msg["Subject"] = message.title
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg.set_content(message.body)

        with smtplib.SMTP(host, port, timeout=20) as server:
            if tls_enabled:
                server.starttls()
            server.login(user, password)
            server.send_message(msg)
        return True

    @staticmethod
    def _format_stdout(message: NotificationMessage) -> str:
        return f"{message.title}\n{message.body}"
